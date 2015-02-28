#!/usr/bin/env python

import bioblend.galaxy as bg
import importlib
import inspect
import os
from docutils.core import publish_doctree, publish_from_doctree  #, publish_parts
#from lxml import etree
import xml.etree.ElementTree as etree

sections = ['tools']# ['datasets', 'genomes', 'histories', 'libraries', 'quotas', 'tools', 'toolshed', 'users', 'visual', 'workflows']
TEMPLATE = """
import click

from parsec import options
from parsec.cli import pass_context
from parsec.io import info
from parsec.galaxy import get_galaxy_instance
from parsec.decorators import bioblend_exception, dict_output

@click.command('%(command_name)s')
@options.galaxy_instance()

%(click_arguments)s
%(click_options)s
@pass_context
@bioblend_exception
@dict_output

def cli(ctx, %(args_with_defaults)s):
    \"\"\"%(short_docstring)s
    \"\"\"
    gi = get_galaxy_instance(galaxy_instance)

    return %(wrapped_method)s(%(wrapped_method_args)s)
"""

def __click_option(name='arg', helpstr='TODO'):
    return '\n'.join([
        '@click.option(',
        '    "--%s",' % name,
        '    help="%s"' % helpstr,
        ')'
    ])

def __click_argument(name='arg'):
    return '@click.argument("%s")' % name

def load_module(module_path):
    name = '.'.join(module_path)
    return importlib.import_module(name)

def boring(section, method_name):
    if method_name.startswith('_'):
        return True
    if method_name.startswith('set_') or method_name.startswith('get_'):
        return True

    func = getattr(getattr(gi, section), method_name)
    if str(type(func)) == "<type 'instancemethod'>":
        return False
    else:
        return True

def important_doc(docstring):
    good = []
    if docstring is not None and len(docstring) > 0:
        for line in docstring.split('\n')[1:]:
            if line.strip() == '':
                return ' '.join(good)
            else:
                good.append(line.strip())
        return ' '.join(good)
    else:
        return "Warning: Undocumented Method"


gi = bg.GalaxyInstance('http://localhost:8000', 'Dummy')
for section in sections:
    for candidate in [x for x in dir(getattr(gi, section)) if not boring(section, x)]:
        func = getattr(getattr(gi, section), candidate)

        argspec = inspect.getargspec(func)
        argdoc = func.__doc__

        data = {
            'command_name': candidate,
            'click_arguments': "",
            'click_options': "",
            'args_with_defaults': "galaxy_instance",
            'wrapped_method_args': "",
        }

        doctree = publish_doctree(argdoc).asdom()
        #<?xml version="1.0"?>
        #<document source="<string>">  # Yes, malformed XML. Truly.
        #<block_quote>
            #<paragraph>Get details of a given tool.</paragraph>
            #<field>
                #<field_name>param link_details</field_name>
                #<field_body>
                #<paragraph>if True, get also link details</paragraph>
                #</field_body>
            #</field>
            #</field_list>
        #</block_quote>
        #</document>

        #print publish_doctree(argdoc)
        doctree = etree.fromstring(doctree.toxml())
        #print publish_from_doctree(publish_doctree(argdoc))
        #import pprint; pprint.pprint(publish_parts(argdoc))
        #for field in doctree.findall('.//field_list/field'):
            #for child in field.getchildren():
                #pass

        # Ignore with only cls/self
        if len(argspec.args) > 1:
            method_signature = ['galaxy_instance']
            # Args and kwargs are separate, as args should come before kwargs
            method_signature_args = []
            method_signature_kwargs = []
            method_exec_args = []
            method_exec_kwargs = []

            for i, k in enumerate(argspec.args[1:]):
                # Sometimes deafults = None when it should = (None)
                # So we hack around this
                try:
                    v = argspec.defaults[i-1]
                except Exception, e:
                    v = None

                # If v is not None, then it's a kwargs, otherwise an arg
                if v is not None:
                    # Strings must be treated specially by removing their value
                    if isinstance(v, str):
                        v = '""'
                    # All other instances of V are fine, e.g. boolean=False or int=1000

                    # Register twice as the method invocation uses v=k
                    method_signature_kwargs.append("%s=%s" % (k, v))
                    method_exec_kwargs.append('%s=%s' % (k, k))

                    # TODO: refactor
                    data['click_options'] += __click_option(name=k, helpstr="TODO")
                else:
                    # Args, not kwargs
                    method_signature_args.append(k)
                    method_exec_args.append(k)
                    data['click_arguments'] += __click_argument(name=k)


            # Complete args
            data['args_with_defaults'] = ', '.join(method_signature +
                                                   method_signature_args +
                                                   method_signature_kwargs)
            data['wrapped_method_args'] = ', '.join(method_exec_args +
                                                    method_exec_kwargs)

        # My function is more effective until can figure out docstring
        data['short_docstring'] = important_doc(argdoc)
        # Full method call
        data['wrapped_method'] = 'gi.%s.%s' % (section, candidate)

        # Generate a command name, prefix everything with auto_ to identify the
        # automatically generated stuff
        cmd_name = 'cmd_auto_%s.py' % candidate
        cmd_path = os.path.join('parsec', 'commands', cmd_name)

        # Save file
        with open(cmd_path, 'w') as handle:
            handle.write(TEMPLATE % data)
