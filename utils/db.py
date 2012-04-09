import json
from django.http import HttpResponse

from tiote import sql
import fns

def rpr_query(request, query_type, query_data=None):
    conn_params = fns.get_conn_params(request)
    # common queries that returns success state as a dict only
    no_return_queries = ('create_user', 'drop_user', 'create_db','create_table',
        'drop_table', 'empty_table', 'delete_row', 'create_column', 'delete_column',)
    
    if query_type in no_return_queries:
        conn_params['db'] = request.GET.get('db') if request.GET.get('db') else conn_params['db']
        q = sql.generate_query( query_type, conn_params['dialect'],query_data)
        result = sql.short_query(conn_params, q)
        return HttpResponse( json.dumps(result) )
    
    # specific queries with implementations similar to both dialects
    elif query_type == 'user_rpr':
        if conn_params['dialect'] == 'mysql':
            conn_params['db'] = 'mysql'
        r = sql.full_query(conn_params, 
            sql.stored_query(request.GET.get('query'),conn_params['dialect']) )
        if type(r) == dict:
            return jsonize_result(r)
        else:
            return fns.http_500(r)
        
        
    elif query_type in ('indexes', 'primary_keys'):
        if query_data is None:
            query_data = {'db':request.GET.get('db'),'tbl':request.GET.get('tbl')}
            if request.GET.get('schm'):
                query_data['schm'] = request.GET.get('schm')
        
        if conn_params['dialect'] == 'postgresql': conn_params['db'] = query_data['db']
        r = []
        for q in sql.generate_query(query_type, conn_params['dialect'], query_data):
            r.append(sql.full_query(conn_params, q) )
        # format postgresql
        
        return r[0]
        
    elif query_type in ('get_row',):
        sub_q_data = {'tbl': request.GET.get('tbl'),'db':request.GET.get('db')}
        sub_q_data['offset'] = request.GET.get('offset') if request.GET.get('offset') else 0
        sub_q_data['limit'] = request.GET.get('limit') if request.GET.get('limit') else 100
        if request.GET.get('schm'):
            sub_q_data['schm'] = request.GET.get('schm')
        # generate where statement
        sub_q_data['where'] = ""
        for ind in range(len(request.POST)):
            sub_q_data['where'] += request.POST.keys()[ind].strip() + "=" 
            sub_q_data['where'] += request.POST.values()[ind].strip()
            if ind != len(request.POST) - 1: sub_q_data['where'] += ' AND '
        # retrieve and run queries
        conn_params['db'] = request.GET.get('db')
        # assert False
        q = sql.generate_query(query_type, conn_params['dialect'], sub_q_data)
        r =  sql.full_query(conn_params, q[0])
        # prepare html
        html = ""
        for ind in range(len(r['columns'])):
            html += '<span class="column-entry">' + str(r['columns'][ind]) + '</span>'
            html += '<br /><div class="data-entry"><code>' + str(r['rows'][0][ind]) + '</code></div>'
        # replace all newlines with <br /> because html doesn't render newlines (\n) directly
        html = html.replace('\n', '<br />')
        return html

    elif query_type in ('table_rpr', 'table_structure',):
        conn_params['db'] = request.GET.get('db')
        sub_q_data = {'db': request.GET.get('db'),}
        if request.GET.get('tbl'):
            sub_q_data['tbl'] = request.GET.get('tbl')
        if request.GET.get('schm'):
            sub_q_data['schm'] = request.GET.get('schm')
        # make query
        r = sql.full_query(conn_params,
            sql.generate_query(query_type, conn_params['dialect'], sub_q_data)[0] )
        # further needed processing
        if conn_params['dialect'] == 'postgresql' and query_type =='table_structure':
            rwz = []
            for tuple_row in r['rows']:
                row = list(tuple_row)
                if row[1] in ('bit', 'bit varying', 'character varying', 'character') and type(row[4]) is int:
                    row[1] += '({0})'.format(row[4])
                elif row[1] in ('numeric', 'decimal') and type(row[5]) is int or type(row[6]) is int:
                    row[1] += '({0},{1})'.format(row[5], row[6])
                elif row[1] in ('interval', 'time with time zone', 'time without time zone',
                    'timestamp with time zone', 'timestamp without time zone') and type(row[7]) is int:
                    row[1] += '({0})'.format(row[7])
                # append the current row to rwz
                rwz.append([row[0], row[1], row[2], row[3] ])
            # change r['rows']
            r['rows'] = rwz
            r['columns'] = [ r['columns'][0], r['columns'][1], r['columns'][2], r['columns'][3] ]
        return r
        
    elif query_type == 'browse_table':
        # initializations        
        sub_q_data = {'tbl': request.GET.get('tbl'),'db':request.GET.get('db')}
        sub_q_data['offset'] = request.GET.get('offset') if request.GET.get('offset') else 0
        sub_q_data['limit'] = request.GET.get('limit') if request.GET.get('limit') else 100
        for item in ['schm', 'sort_key', 'sort_dir']:
            if request.GET.get(item): sub_q_data[item] = request.GET.get(item)
        # retrieve and run queries
        conn_params['db'] = request.GET.get('db')
        keys = rpr_query(request, 'primary_keys', sub_q_data)
        count = sql.full_query(conn_params, 
            sql.generate_query('count_rows', conn_params['dialect'], sub_q_data)[0],
            )['rows']
        r = sql.full_query(conn_params,
            sql.generate_query(query_type, conn_params['dialect'], sub_q_data)[0]
            )
        # format and return data
        if type(r) == dict:
            r.update({'total_count': count[0][0], 'offset': sub_q_data['offset'],
                      'limit':sub_q_data['limit'], 'keys': keys})
            return r
        else:
            return fns.http_500(r)
        
    # queries that just asks formats and return result
    elif query_type in ('existing_tables',):
        query_data = {'db':request.GET.get('db'),'tbl':request.GET.get('tbl')}
        if conn_params['dialect'] == 'postgresql':
            query_data['schm'] = request.GET.get('schm')
            conn_params['db'] = query_data['db']
            
        q = sql.generate_query(query_type, conn_params['dialect'], query_data)
        r =  sql.full_query(conn_params,
            q[0])
        return r['rows']

        
    # queries with dissimilar implementations
    elif conn_params['dialect'] == 'postgresql':
        
        if query_type == 'table_list':
            # change default database
            if 'db' in query_data:
                conn_params['db'] = query_data['db']
            return sql.full_query(conn_params,
                sql.stored_query(query_type, conn_params['dialect']))
        
        else:
            return fns.http_500('query not implemented!')
            
            
    elif conn_params['dialect'] == 'mysql':
        
        if query_type == 'describe_databases':
            conn_params['db'] = 'INFORMATION_SCHEMA';
            query = sql.stored_query(query_type, conn_params['dialect'])
            return sql.full_query(conn_params, query)
        
        else:
            return fns.http_500('query not yet implemented!')
    else:
        return fns.http_500('dialect not supported!')


def common_query(request, query_name):
    conn_params = fns.get_conn_params(request)
    pgsql_redundant_queries = ('template_list', 'group_list', 'user_list', 'db_list', 'schema_list')
    mysql_redundant_queries = ('db_list','charset_list', 'supported_engines')
    
    if conn_params['dialect'] == 'postgresql' and query_name in pgsql_redundant_queries :
            # this kind of queries require no special attention
            conn_params['db'] == request.GET.get('db') if request.GET.get('db') else conn_params['db']
            r = sql.full_query(conn_params,
                sql.stored_query(query_name, conn_params['dialect']))
            return r['rows']
                
    elif conn_params['dialect'] == 'mysql':
        
        if query_name == 'db_names':
            db_names =  sql.get_databases( fns.get_conn_params(request) )
            return result_to_json(db_names)
        
        elif query_name == 'describe_databases':
            result = rpr_query(request, query_name)
            d = SortedDict()
            for tup in result['rows']:
                if tup[0] not in d:
                    d[ tup[0] ] = []
                d[ tup[0] ].append((tup[1],tup[2]))
            return json.dumps(d)
        
        elif query_name in mysql_redundant_queries :
            # this kind of queries require no special attention
            return sql.full_query(conn_params,
                sql.stored_query(query_name, conn_params['dialect']))['rows']


def do_login(request, cleaned_data):
    host = cleaned_data['host']
    username = cleaned_data['username']
    password = cleaned_data['password']
    database_driver = cleaned_data['database_driver']
    dict_post = {'username':username,'password':password,'database_driver':database_driver, 'host':host}
    if 'connection_database' in cleaned_data:
        dict_post['connection_database'] = cleaned_data['connection_database']
    dict_cd = sql.model_login(dict_post)
    if not dict_cd['login']:
        #authentication failed
        return dict_cd
    
    else:
        # authentication succeeded
        request.session['TT_LOGIN'] = 'true'
        request.session['TT_USERNAME'] = username
        request.session['TT_PASSWORD'] = password
        request.session['TT_DIALECT'] = database_driver
        request.session['TT_HOST'] = host
        if 'connection_database' in dict_post:
            request.session['TT_DATABASE'] = dict_post['connection_database']
        return dict_cd
    

def get_home_variables(request):
    p = fns.get_conn_params(request)
    variables = {'user': p['username'], 'host': p['host']}
    variables['dialect'] = 'PostgreSQL' if p['dialect'] == 'postgresql' else 'MySQL'
    result = sql.full_query( p, sql.stored_query('variables', p['dialect']))
    if p['dialect'] == 'postgresql':
        variables['version'] = result['rows'][0]
        return variables
    elif p['dialect'] == 'mysql':
        if type(result) == dict:
            ll = result['rows']
            d = {}
            for i in range( len(ll) ):
                  d[ll[i][0]] = ll[i][1]  
            variables.update(d)
            return variables
        else:
            return fns.http_500(result)


