import datetime
# sqlaclehemy modules
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import URL
from sqlalchemy.exceptions import OperationalError, ProgrammingError, DatabaseError

def stored_query(query, dialect):
    # db of stored queries
    stored_query_db = {
        'postgresql': {
            'variables':
                "SHOW server_version",
            'template_list':
                "SELECT datname FROM pg_database",
            'group_list':
                "SELECT rolname FROM pg_roles WHERE rolcanlogin=False",
            'db_list':
                "SELECT datname FROM pg_database WHERE datistemplate = 'f';",
            'user_rpr': 
                "SELECT rolname, rolcanlogin, rolsuper, rolinherit, rolvaliduntil FROM pg_roles",
            'user_list':
                "SELECT rolname FROM pg_roles",
            'table_list':
                "SELECT schemaname, tablename FROM pg_tables ORDER BY schemaname DESC",
            'existing_tables':
                "SELECT tablename FROM pg_tables WHERE \
                NOT schemaname='information_schema' AND NOT schemaname='pg_catalog'",
        },

        'mysql': {
            'describe_databases': 
                "SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_ROWS FROM `information_schema`.`tables`",
            'db_list':
                "SHOW databases",
            'user_rpr':
                "SELECT user.`Host`, user.`User` FROM user",
            'user_list':
                "SELECT user.`User` FROM user",
            'supported_engines':
                "SELECT engine, support FROM `information_schema`.`engines` \
                WHERE support='yes' OR support='default'",
            'charset_list':
                "SELECT CHARACTER_SET_NAME FROM INFORMATION_SCHEMA.CHARACTER_SETS",
            'variables':
                '''SHOW SESSION VARIABLES WHERE `Variable_name`='version_compile_machine' 
                OR `Variable_name`='version_compile_os' OR `variable_name`='version'
                '''     
        }
    }        
    
    # 
    return stored_query_db[dialect][query]


def generate_query(query_type, dialect='postgresql', query_data=None):
    if dialect == 'postgresql': #postgresql-only statements
        
        if query_type == 'create_user':
            # create role statement
            q0 = "CREATE ROLE {role_name}".format(**query_data)
            if query_data['can_login']:
                q0 += " LOGIN"
            if query_data['password']:
                q0 += " ENCRYPTED PASSWORD '{password}'".format(**query_data)
            if query_data['role_privileges']:
                for option in query_data['role_privileges']:
                    q0 += " " + option
            if query_data['connection_limit']:
                q0 += " CONNECTION LIMIT {connection_limit}".format(**query_data)
            if query_data['valid_until']:
                q0 += " VALID UNTIL '{valid_until}'".format(**query_data)
            if query_data['group_membership']:
                q0 += " IN ROLE"
                for grp_index in range( len(query_data['group_membership']) ):
                    if grp_index == len(query_data['group_membership']) - 1:
                        q0 += " " + query_data['group_membership'][grp_index]
                    else:
                        q0 += " " + query_data['group_membership'][grp_index] + ","
#            if query_data['comment']:
#                q1 = "COMMENT ON ROLE {role_name} IS \'{comment}\'".format(**query_data)
#                queries.append(q1)
            queries = (q0, )
            return queries
        elif query_type == 'drop_user':
            queries = []
            for cond in query_data:
                q = "DROP ROLE {rolname}".format(**cond)
                queries.append(q) 
            return tuple(queries)
        
        elif query_type == 'create_db':
            q = "CREATE DATABASE {name}".format(**query_data)
            if query_data['encoding']:
                q += " WITH ENCODING='{encoding}'".format(**query_data)
            if query_data['owner']:
                q += " OWNER={owner}".format(**query_data)
            if query_data['template']:
                q += " TEMPLATE={template}".format(**query_data)
            return (q, )
        
        elif query_type == 'table_rpr':
            q = "SELECT table_name, table_type, table_schema FROM \
                information_schema.tables WHERE table_schema='{schema}'".format(**query_data)
            return (q, )
        
        elif query_type == 'count_rows':
            added_q0 = 'information_schema.' if query_data['schema'] =='information_schema' else ''
            q0 = "SELECT count(*) FROM "+added_q0+"{table}".format(**query_data)
            return (q0,)
        
        elif query_type == 'browse_table':
            added_q0 = 'information_schema.' if query_data['schema'] =='information_schema' else ''
            q0 = "SELECT * FROM "+added_q0+"{table} LIMIT {limit} OFFSET {offset}".format(**query_data)
            return (q0,)
        
        elif query_type == 'delete_row':
            queries = []
            for whereCond in query_data['conditions']:
                added_q0 = 'information_schema.' if query_data['schema'] == 'information_schema' else ''
                q0 = "DELETE FROM "+added_q0+"{table}".format(**query_data) + " WHERE "+whereCond
                queries.append(q0)
            return tuple(queries)
        
        elif query_type == 'table_keys':
            q0 = "SELECT constraint_name, column_name FROM information_schema.key_column_usage \
WHERE table_catalog='{database}' AND table_schema='{schema}' AND table_name='{table}'\
 AND constraint_name like '%_pkey%'".format(**query_data)
            return (q0,)
        
    elif dialect == 'mysql': # mysql-only statements

        if query_type == 'create_user':
            # create user statement
            queries = []
            q1 = "CREATE USER '{username}'@'{host}'".format(**query_data)
            if query_data['password']:
                q1 += " IDENTIFIED BY '{password}'".format(**query_data)
            
            queries.append(q1)
            # grant privileges
            q2 = "GRANT"
            if query_data['privileges'] == 'all':
                q2 += " ALL"
            elif query_data['privileges'] == 'select':
                priv_groups = ['user_privileges','administrator_privileges']
                for priv_group in priv_groups:
                    for priv_in in range( len(query_data[priv_group])):
                        if priv_in == len(query_data[priv_group]) - 1:
                            q2 += ' ' + query_data[priv_group][priv_in]
                        else:
                            q2 += ' ' + query_data[priv_group][priv_in] + ','
                            
            if query_data['select_databases'] and len(query_data['select_databases']) > 1:
                for db in query_data['select_databases']: #mutliple grant objects
                    q3 = q2 + ' ON {database}.*'.format(database = db)
                    # user specification
                    q3 += " TO '{username}'@'{host}'".format(**query_data)
                    # grant option
                    if query_data['options']:
                        q3 += " WITH {options[0]}".format(**query_data)
                    # append generated query to queries
                    queries.append(q3)
            else:
                # database access
                if query_data['access'] == 'all':
                    q4 = q2 + ' ON *.*'
                elif query_data['access'] == 'select':
                    q4 = q2 + ' ON {select_databases[0]}.*'.format(**query_data)
                    
                # user specification
                q4 += " TO '{username}'@'{host}'".format(**query_data)
                # grant option
                if query_data['options']:
                    q4 += " WITH {options[0]}".format(**query_data)
                queries.append(q4)
            return tuple( queries )
        
        elif query_type == 'create_db':
            q = "CREATE DATABASE {name}".format(**query_data)
            if query_data['charset']:
                q += " CHARACTER SET {charset}".format(**query_data)
            return (q, )
        
        elif query_type == 'create_table':
            q = "CREATE TABLE `{db}`.`{name}`".format(**query_data)
            
            sub_form_count = query_data.pop('sub_form_count')
            if sub_form_count != 0:
                q += ' ('
                l_primary = []
                l_index = []
                l_unique = []
                for fi in range(sub_form_count):
                    if query_data['key_'+str(fi)]:
                        if query_data['key_'+str(fi)] == 'primary':
                            l_primary.append( query_data['name_'+str(fi)] )
                        elif query_data['key_'+str(fi)] == 'unique':
                            l_unique.append( query_data['name_'+str(fi)] )
                        elif query_data['key_'+str(fi)] == 'index':
                            l_index.append( query_data['name_'+str(fi)] )
                    sub_q = ' {name_'+str(fi)+'} {type_'+str(fi)+'}'
                    # types with binary
                    if query_data['type_'+str(fi)] in ['tinytext','text','mediumtext','longtext']:
                        sub_q += ' BINARY' if 'binary' in query_data['other_'+str(fi)] else ''
                    # types with length
                    if query_data['type_'+str(fi)] in ['bit','tinyint','smallint','mediumint','int','integer','bigint',
                                      'real','double','float','decimal','numeric','char','varchar',
                                      'binary','varbinary']:
                        sub_q += '({size_'+str(fi)+'})' if query_data['size_'+str(fi)] else ''
                    # types with unsigned
                    if query_data['type_'+str(fi)] in ['tinyint','smallint','mediumint','int','integer','bigint',
                                      'real','double','float','decimal','numeric']:
                        sub_q += ' UNSIGNED' if 'unsigned' in query_data['other_'+str(fi)] else ''
                    # types needing values
                    if query_data['type_'+str(fi)] in ['set','enum']:
                        sub_q += ' {values_'+str(fi)+'}' if query_data['values_'+str(fi)] else ''
                    # types needing charsets
                    if query_data['type_'+str(fi)] in ['char','varchar','tinytext','text',
                                            'mediumtext','longtext','enum','set']:
                        sub_q += ' CHARACTER SET {charset_'+str(fi)+'}'
                    # some options
                    sub_q += ' NOT NULL' if 'not null' in query_data['other_'+str(fi)] else ' NULL'
                    s_d = query_data['default_'+str(fi)]
                    if s_d:
                        if query_data['type_'+str(fi)] not in ['tinyint','smallint','mediumint','int','integer','bigint',
                                          'bit','real','double','float','decimal','numeric']:
                            sub_q += ' DEFAULT \''+s_d+'\''
                        else:
                            sub_q += ' DEFAULT '+s_d+''
#                    sub_q += ' DEFAULT {default_'+str(fi)+'}' if query_data['default_'+str(fi)] else ''
                    sub_q += ' AUTO_INCREMENT' if 'auto increment' in query_data['other_'+str(fi)] else ''
                    # append to query
                    q += sub_q if fi == sub_form_count-1 else sub_q + ','
            
                # handle keys: primary, index and unique
                if l_index:
                    sub_q = ', INDEX ('
                    for i in range(len(l_index)):
                        sub_q += ' '+l_index[i] +')' if i == len(l_index) - 1 else ' '+l_index[i]+','
                        q += sub_q
                if l_unique:
                    sub_q = ', UNIQUE ('
                    for i in range(len(l_unique)):
                        sub_q += ' '+l_unique[i] +')' if i == len(l_unique) - 1 else ' '+l_unique[i]+','
                        q += sub_q
                if l_primary:
                    sub_q = ', PRIMARY KEY ('+l_primary[0]+')'
                    q += sub_q
            q += ')' if sub_form_count != 0 else ''
            q += " CHARACTER SET {charset} ENGINE {engine}"
            q = q.format(**query_data)
            return (q, )
        
        elif query_type == 'drop_table':
            queries = []
            db = query_data.pop('db')
            for where in query_data['conditions']:
                queries.append( "DROP TABLE "+db+".{table_name}".format(**where))
            return tuple(queries)
        
        elif query_type == 'empty_table':
            queries = []
            db = query_data.pop('db')
            for where in query_data['conditions']:
                queries.append( "TRUNCATE "+db+".{table_name}".format(**where) )
            return queries
        
        elif query_type == 'column_list':
            return ("SELECT column_name FROM information_schema.columns WHERE table_schema='{db}' AND table_name='{table}")
        
        elif query_type == 'drop_user':
            queries = []
            for where in query_data:
                q = "DROP USER '{user}'@'{host}'".format(**where)
                queries.append(q)
            return tuple(queries)
        
        elif query_type == 'delete_row':
            queries = []
            for where in query_data['conditions']:
                queries.append("DELETE FROM {database}.{table}".format(**query_data) + " WHERE "+where+" LIMIT 1" )
            return queries
                
        elif query_type == 'indexes':
            return ("SHOW indexes FROM `{database}`.`{table}`".format(**query_data), )
                
        elif query_type == 'table_rpr':
            q = "SELECT TABLE_NAME, TABLE_ROWS, TABLE_TYPE, ENGINE FROM \
            `INFORMATION_SCHEMA`.`TABLES` WHERE TABLE_SCHEMA = '{database}'".format(**query_data)
            return (q,)

        elif query_type == 'count_rows':
            q0 = "SELECT count(*) FROM `{database}`.`{table}`".format(**query_data)
            return (q0, )
        
        elif query_type == 'browse_table':
            q0 = "SELECT * FROM `{database}`.`{table}` LIMIT {limit} OFFSET {offset}".format(**query_data)
            return (q0,)
        
        elif query_type == 'table_keys':
            
            q0 = "SELECT CONSTRAINT_NAME, COLUMN_NAME FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE \
                WHERE TABLE_SCHEMA='{database}' AND TABLE_NAME='{table}' AND CONSTRAINT_NAME='PRIMARY'".format(**query_data)
            return (q0, )
        else:
            return None



def full_query(conn_params, query):
    '''
    executes and returns a query result
    '''
    eng = create_engine(get_conn_link(conn_params))
    conn = eng.connect()
    try:
        conn = eng.connect()
        query_result =  conn.execute(text(query))
        d = {}
        l = []
        for row in query_result:
            row = list(row)
            for i in range(len(row)):
                if type( row[i] ) == datetime.datetime:
                    row[i] = row[i].__str__()
            l.append( tuple(row) )
        d =  {'columns': query_result.keys(),'count': query_result.rowcount, 
            'rows': l}
        conn.close()
        return d
    except Exception as e:
        conn.close()
        return str(e)
    
    
def short_query(conn_params, queries):
    """
    executes and returns the success state of the query
    """
    eng = create_engine( get_conn_link(conn_params) )
    conn = ''
    try:
        conn = eng.connect()
        for query in queries:
            query_result = conn.execute(text(query))
        return {'status':'successfull', }
    except Exception as e:
        conn.close()
        return {'status':'failed', 'msg': str(e) }
    
    
def model_login(conn_params):
    link = URL(conn_params['database_driver'], username = conn_params['username'],
        password= conn_params['password'], host = conn_params['host'])
    if conn_params['connection_database']:
        link.database = conn_params['connection_database']
    elif not conn_params['connection_database'] and conn_params['database_driver'] == 'postgresql':
        link.database = 'postgres'
    engine = create_engine(link)
    conn = ''
    dict_ret = {}
    try:
        conn = engine.connect()
    except OperationalError as e:
        dict_ret =  {'login': False, 'msg': str(e)}
    else:
        # todo 'msg'
        dict_ret =  {'login': True, 'msg': ''}
        conn.close()
    return dict_ret
 


def get_conn_link(conn_params):
    return '{dialect}://{username}:{password}@{host}/{database}'.format(**conn_params)


