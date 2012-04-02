import json

from django.http import HttpResponse, Http404
from django.template import loader, RequestContext, Template
from django.views.decorators.http import require_http_methods

from tiote import forms, utils


def overview(request):
    # table deletion or emptying request catching and handling
    if request.method == 'POST' and request.GET.get('update'):
        l = request.POST.get('whereToEdit').strip().split(';');
        conditions = utils.fns.get_conditions(l)
        q = ''
        if request.GET.get('update') == 'drop':
            q = 'drop_table'
        elif request.GET.get('update') == 'empty':
            q = 'empty_table'
        query_data = {'database':request.GET['database'],'conditions':utils.fns.get_conditions(l)}
        if request.GET.get('schema'):
            query_data['schema'] = request.GET.get('schema')
        return utils.db.rpr_query(request, q , query_data)

    tbl_data = utils.db.rpr_query(request, 'table_rpr')
    from urllib import urlencode
    from django.utils.datastructures import SortedDict
    dest_url = SortedDict({'section':'table','view':'browse'})
    dest_url['database'] = request.GET.get('database')
    dest_url['schema'] = request.GET.get('schema')
    props_keys = [('table_name', 'key')]
    if utils.fns.get_conn_params(request)['dialect'] == 'postgresql':
        props_keys.append(('table_schema', 'key'))
    static_addr = utils.fns.render_template(request, '{{STATIC_URL}}')
    tables_html = utils.fns.HtmlTable(static_addr=static_addr,
        props={'count':tbl_data['count'],'with_checkboxes': True,
            'go_link': True, 'go_link_type': 'href', 
            'go_link_dest': '#'+urlencode(dest_url)+'&table',
            'keys': props_keys
        }, **tbl_data
        ).to_element()
    table_options_html = utils.fns.table_options('data')
    return HttpResponse(table_options_html + tables_html)
    

def route(request):
    if request.GET['view'] == 'overview':
        return overview(request)
