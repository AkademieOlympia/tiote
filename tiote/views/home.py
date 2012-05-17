import json, httplib

from django.http import HttpResponse, Http404
from django.template import loader, RequestContext, Template
from django.views.decorators.http import require_http_methods
from django.forms.formsets import formset_factory

from tiote import forms, utils, VERSION


def home(request):
    conn_params = utils.fns.get_conn_params(request)
    # queries and initializations
    # template_list = utils.db.common_query(request, 'template_list')
    # user_list = utils.db.common_query(request, 'user_list');
    # charset_list = utils.db.common_query(request, 'charset_list');
    
    # DbForm = forms.get_dialect_form('DbForm', conn_params['dialect'])
    
    # if request.method == 'POST':
    #     form = DbForm(templates=template_list, users=user_list,
    #         charsets=charset_list, data=request.POST)
    #     if form.is_valid():
    #         return utils.db.rpr_query(conn_params, 'create_db', form.cleaned_data)
    # else:
    #     form = DbForm(templates=template_list, users=user_list, charsets=charset_list)
    
    extra_vars={
        # 'form':form, 
        'variables':utils.db.get_home_variables(request)
    }
    try:
        # get version information
        conn = httplib.HTTPSConnection("github.com", timeout=10) # should be change to github project page
                                                                # only stable static link available
        conn.request("GET", "/dumb906/tiote/raw/master/docs/changelog.rst") # path to changelog
        r = conn.getresponse()
        if r.status != httplib.OK:
            raise Exception # the exception would be caught by an empty except block
                            # skips the else block if the response status is not 200
    except Exception: pass
    else :
        lines = r.read().split("\n")
        for i in xrange(0, len( lines) ):
            if not lines[i].startswith("-"): continue # not the needed line

            j = i - 1 # index to start response string
            if not lines[j].split(" ")[0] > VERSION:
                break # exit loop since the versions are same
            
            # if the details of the update should be included, uncomment the following lines

            # # loop from the next line after index i until the next line that starts with "-"
            # # when found add the contents from the last index of "-" to the next index of "-"
            # for i_2 in xrange(i + 1, len(lines)):
            #     if not lines[i_2].startswith("-"): continue # not the needed line

            #     _l.extend( lines[i+1:i_2] ) # extend with a slice from the index searching started 
            #                                 # - from to the index that satisfies the search
            #     break
            # # format ``_l`` and add it to the variables for the next page
            # extra_vars.update({'version_str': VERSION, 'new_version_str': lines[j],
            #     'version_changelog': "<br />".join(_l), 'version_update': True 
            # })

            # make the version information available to the template file
            extra_vars.update({'version_update': True, 'version_str': VERSION,
                'new_version_str': lines[j].split(" ")[0], 
                'new_version_release_date': lines[j].split(" ", 2)[-1].replace("*", "") # added a limit 'cause
                                                                                        # d date string includes
                                                                                        # d delimmiter " "
            })

            break # done what we need; can now exit loop

    return utils.fns.response_shortcut(request, extra_vars=extra_vars)

def dbs(request):
    if request.method == 'POST':
        pass

    # view things



def route(request):
    if request.GET.get('v') in ('home', 'hm'):
        return home(request)

    # default action
    return home(request)
    
