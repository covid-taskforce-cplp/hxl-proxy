"""
Controllers for the HXL Proxy
David Megginson
January 2015

License: Public Domain
Documentation: http://hxlstandard.org
"""

from urllib2 import urlopen
import sys

from flask import Response, request, render_template, url_for, stream_with_context, redirect

from hxl_proxy import app
from hxl_proxy.profiles import addProfile, updateProfile, getProfile

from hxl.io import HXLReader, genHXL, genJSON
from hxl.schema import readHXLSchema
from hxl.filters import parse_tags, fix_tag
from hxl.filters.clean import HXLCleanFilter
from hxl.filters.count import HXLCountFilter
from hxl.filters.cut import HXLCutFilter
from hxl.filters.merge import HXLMergeFilter
from hxl.filters.sort import HXLSortFilter
from hxl.filters.select import HXLSelectFilter, parse_query
from hxl.filters.validate import HXLValidateFilter

@app.route("/")
def home():
    return render_template('home.html', args=request.args)
    
@app.route("/filters/new")
@app.route("/data/<key>/edit")
def edit_filter(key=None):
    if key:
        args = getProfile(str(key))
    else:
        args = request.args
    return render_template('filter-edit.html', key=key, args=args)

@app.route("/actions/save-filter", methods=['POST'])
def save_filter():
    key = request.form.get('key')
    if key:
        updateProfile(str(key), request.form)
    else:
        key = addProfile(request.form)
    return redirect("/data/" + key, 303)

@app.route("/validate")
def validate():
    format = 'html' # fixme
    url = request.args.get('url', None)
    schema_url = request.args.get('schema_url', None)
    show_all = (request.args.get('show_all') == 'on')
    source = None
    if url:
        source = HXLReader(urlopen(url))
        schema_source = None
        if schema_url:
            schema = readHXLSchema(HXLReader(urlopen(schema_url)))
        else:
            schema = readHXLSchema()
        source = HXLValidateFilter(source=source, schema=schema, show_all=show_all)
        
    if format == 'json':
        return Response(genJSON(source), mimetype='application/json')
    elif format == 'html':
        return Response(stream_with_context(stream_template('validate.html', url=url, schema_url=schema_url, show_all=show_all, source=source)))
    else:
        return Response(genHXL(source), mimetype='text/csv')

@app.route("/filters/preview")
@app.route("/data/<key>")
@app.route("/data/<key>.<format>")
def filter(key=None, format="html"):
    if key:
        # look up a saved filter
        args = getProfile(str(key))
    else:
        # use GET parameters
        args = request.args

    name = args.get('name', 'Filtered HXL dataset')
    url = args['url']
    input = urlopen(url)
    source = HXLReader(input)
    filter_count = int(args.get('filter_count', 5))
    for n in range(1,filter_count+1):
        filter = args.get('filter%02d' % n)
        if filter == 'clean':
            upper_tags = parse_tags(args.get('clean-upper_tags%02d' % n, ''))
            lower_tags = parse_tags(args.get('clean-lower_tags%02d' % n, ''))
            date_tags = parse_tags(args.get('clean-date_tags%02d' % n, ''))
            number_tags = parse_tags(args.get('clean-number_tags%02d' % n, ''))
            source = HXLCleanFilter(source, upper=upper_tags, lower=lower_tags, date=date_tags, number=number_tags)
        elif filter == 'count':
            tags = parse_tags(args.get('count-tags%02d' % n, ''))
            aggregate_tag = args.get('count-aggregate_tag%02d' % n)
            if aggregate_tag:
                aggregate_tag = fix_tag(aggregate_tag)
            else:
                aggregate_tag = None
            source = HXLCountFilter(source, tags=tags, aggregate_tag=aggregate_tag)
        elif filter == 'cut':
            include_tags = parse_tags(args.get('cut-include_tags%02d' % n, []))
            exclude_tags = parse_tags(args.get('cut-exclude_tags%02d' % n, []))
            source = HXLCutFilter(source, include_tags=include_tags, exclude_tags=exclude_tags)
        elif filter == 'merge':
            tags = parse_tags(args.get('merge-tags%02d' % n, []))
            keys = parse_tags(args.get('merge-keys%02d' % n, []))
            before = (args.get('merge-before%02d' % n) == 'on')
            url = args.get('merge-url%02d' % n)
            merge_source = HXLReader(url=url)
            source = HXLMergeFilter(source, merge_source, keys, tags, before)
        elif filter == 'select':
            query = parse_query(args['select-query%02d' % n])
            reverse = (args.get('select-reverse%02d' % n) == 'on')
            source = HXLSelectFilter(source, queries=[query], reverse=reverse)
        elif filter == 'sort':
            tags = parse_tags(args.get('sort-tags%02d' % n, ''))
            reverse = (args.get('sort-reverse%02d' % n) == 'on')
            source = HXLSortFilter(source, tags=tags, reverse=reverse)

    if format == 'json':
        return Response(genJSON(source), mimetype='application/json')
    elif format == 'html':
        return Response(stream_with_context(stream_template('filter-preview.html', title=name, source=source, args=args, key=key)))
    else:
        return Response(genHXL(source), mimetype='text/csv')

@app.route('/data/<key>/chart')
def chart(key=None):
    profile = getProfile(key)
    tag = request.args.get('tag', '#x_count_num')
    type = request.args.get('type', 'pie')
    return render_template('chart.html', key=key, args=profile, tag=tag, type=type)

app.jinja_env.globals['static'] = (
    lambda filename: url_for('static', filename=filename)
)

def decode(s):
    try:
        return unicode(s, 'utf-8')
    except:
        return s

app.jinja_env.globals['unicode'] = (
    decode
)

def stream_template(template_name, **context):
    """From the flask docs - stream a long template result."""
    app.update_template_context(context)
    t = app.jinja_env.get_template(template_name)
    rv = t.stream(context)
    rv.enable_buffering(5)
    return rv
