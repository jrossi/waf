#!/usr/bin/env python
# encoding: utf-8
# Matthias Jahn jahn dôt matthias ât freenet dôt de, 2007 (pmarat)

import os, sys, imp, types
from waflib.Tools import ccroot
from waflib import Utils, Configure
from waflib.Logs import debug

c_compiler = {
'win32':  ['msvc', 'gcc'],
'cygwin': ['gcc'],
'darwin': ['gcc'],
'aix':    ['xlc', 'gcc'],
'linux':  ['gcc', 'icc', 'suncc'],
'sunos':  ['gcc', 'suncc'],
'irix':   ['gcc'],
'hpux':   ['gcc'],
'gnu':    ['gcc'],
'java':   ['gcc', 'msvc', 'icc'],
'default':['gcc'],
}

def configure(conf):
	"""
	for each compiler for the platform, try to configure the compiler
	in theory the tools should raise a configuration error if the compiler
	pretends to be something it is not (setting CC=icc and trying to configure gcc)
	"""
	try: test_for_compiler = conf.options.check_c_compiler
	except AttributeError: conf.fatal("Add options(opt): opt.load('compiler_c')")
	for compiler in test_for_compiler.split():
		conf.env.stash()
		conf.start_msg('Checking for %r (c compiler)' % compiler)
		try:
			conf.load(compiler)
		except conf.errors.ConfigurationError as e:
			conf.env.revert()
			conf.end_msg(False)
			debug('compiler_c: %r' % e)
		else:
			if conf.env['CC']:
				conf.end_msg(True)
				conf.env['COMPILER_CC'] = compiler
				break
			conf.end_msg(False)
	else:
		conf.fatal('could not configure a c compiler!')

def options(opt):
	global c_compiler
	build_platform = Utils.unversioned_sys_platform()
	possible_compiler_list = c_compiler[build_platform in c_compiler and build_platform or 'default']
	test_for_compiler = ' '.join(possible_compiler_list)
	cc_compiler_opts = opt.add_option_group("C Compiler Options")
	cc_compiler_opts.add_option('--check-c-compiler', default="%s" % test_for_compiler,
		help='On this platform (%s) the following C-Compiler will be checked by default: "%s"' % (build_platform, test_for_compiler),
		dest="check_c_compiler")
	for x in test_for_compiler.split():
		opt.load('%s' % x)

