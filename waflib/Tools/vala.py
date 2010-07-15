#!/usr/bin/env python
# encoding: utf-8
# Ali Sabil, 2007

import os.path, shutil
from waflib import Task, Runner, Utils, Logs, Build, Node, Options
from waflib.TaskGen import extension, after, before

class valac_task(Task.Task):

	vars = ["VALAC", "VALAC_VERSION", "VALAFLAGS"]
	ext_out = ['.h']

	def run(self):
		env = self.env

		cmd = [env['VALAC'], '-C', '--quiet']
		cmd.extend(env['VALAFLAGS'])

		if self.threading:
			cmd.append('--thread')

		if self.profile:
			cmd.append('--profile=%s' % self.profile)

		if self.target_glib:
			cmd.append('--target-glib=%s' % self.target_glib)

		if getattr(self.generator, 'link_task', []).__class__.__name__.find('program') < 0:
			output_dir = self.outputs[0].bld_dir()
			cmd.append('--library=' + self.target)
			for x in self.outputs:
				if x.name.endswith('.h'):
					cmd.append('--header=' + x.name)
			if hasattr(self, 'gir'):
				cmd.append('--gir=%s.gir' % self.gir)

		for vapi_dir in self.vapi_dirs:
			cmd.append('--vapidir=%s' % vapi_dir)

		for package in self.packages:
			cmd.append('--pkg=%s' % package)

		for package in self.packages_private:
			cmd.append('--pkg=%s' % package)

		cmd.extend([a.abspath() for a in self.inputs])
		result = self.exec_command(cmd, cwd=self.outputs[0].parent.abspath())

		if self.packages and getattr(self, 'deps_node', None):
			self.deps_node.write('\n'.join(self.packages))

		return result

@extension('.vala', '.gs')
def vala_file(self, node):
	valatask = getattr(self, "valatask", None)
	# there is only one vala task and it compiles all vala files .. :-/
	if not valatask:
		valatask = self.create_task('valac')
		self.valatask = valatask # this assumes one vala task by task generator
		self.includes = Utils.to_list(getattr(self, 'includes', []))
		self.uselib = self.to_list(getattr(self, 'uselib', []))
		valatask.packages = []
		valatask.packages_private = Utils.to_list(getattr(self, 'packages_private', []))
		valatask.vapi_dirs = []
		valatask.target = self.target
		valatask.threading = False
		valatask.install_path = getattr(self, 'install_path', '')
		valatask.profile = getattr (self, 'profile', 'gobject')
		valatask.target_glib = None

		packages = Utils.to_list(getattr(self, 'packages', []))
		vapi_dirs = Utils.to_list(getattr(self, 'vapi_dirs', []))
		includes =  []

		if hasattr(self, 'uselib_local'):
			local_packages = Utils.to_list(self.uselib_local)
			seen = []
			while len(local_packages) > 0:
				package = local_packages.pop()
				if package in seen:
					continue
				seen.append(package)

				# check if the package exists
				package_obj = self.bld.get_tgen_by_name(package)
				if not package_obj:
					raise Errors.WafError("object %r was not found in uselib_local (required by %r)" % (package, self.name))
				package_name = package_obj.target
				package_node = package_obj.path
				package_dir = package_node.relpath_gen(self.path)

				for task in package_obj.tasks:
					for output in task.outputs:
						if output.name == package_name + ".vapi":
							valatask.set_run_after(task)
							if package_name not in packages:
								packages.append(package_name)
							if package_dir not in vapi_dirs:
								vapi_dirs.append(package_dir)
							if package_dir not in includes:
								includes.append(package_dir)

				if hasattr(package_obj, 'uselib_local'):
					lst = self.to_list(package_obj.uselib_local)
					lst.reverse()
					local_packages = [pkg for pkg in lst if pkg not in seen] + local_packages

		valatask.packages = packages
		for vapi_dir in vapi_dirs:
			try:
				valatask.vapi_dirs.append(self.path.find_dir(vapi_dir).abspath())
				valatask.vapi_dirs.append(self.path.find_dir(vapi_dir).get_bld().abspath())
			except AttributeError:
				Logs.warn("Unable to locate Vala API directory: '%s'" % vapi_dir)

		self.includes.append(self.bld.srcnode.abspath())
		self.includes.append(self.bld.bldnode.abspath())
		for include in includes:
			try:
				self.includes.append(self.path.find_dir(include).abspath())
				self.includes.append(self.path.find_dir(include).get_bld().abspath())
			except AttributeError:
				Logs.warn("Unable to locate include directory: '%s'" % include)


		if valatask.profile == 'gobject':
			if hasattr(self, 'target_glib'):
				Logs.warn('target_glib on vala tasks is not supported --vala-target-glib=MAJOR.MINOR from the vala tool options')

			if getattr(Options.options, 'vala_target_glib', None):
				valatask.target_glib = Options.options.vala_target_glib

			if not 'GOBJECT' in self.uselib:
				self.uselib.append('GOBJECT')

		if hasattr(self, 'threading'):
			if valatask.profile == 'gobject':
				valatask.threading = self.threading
				if not 'GTHREAD' in self.uselib:
					self.uselib.append('GTHREAD')
			else:
				#Vala doesn't have threading support for dova nor posix
				Logs.warn("Profile %s does not have threading support" % valatask.profile)

		if hasattr(self, 'gir'):
			valatask.gir = self.gir

	valatask.inputs.append(node)
	c_node = node.change_ext('.c')

	valatask.outputs.append(c_node)
	self.source.append(c_node)

	features = self.features
	if not 'cprogram' in features:
		valatask.outputs.append(self.path.find_or_declare('%s.h' % self.target))
		valatask.outputs.append(self.path.find_or_declare('%s.vapi' % self.target))

		if hasattr(self, 'gir'):
			valatask.outputs.append(self.path.find_or_declare('%s.gir' % self.gir))

		if valatask.packages:
			d = self.path.find_or_declare('%s.deps' % self.target)
			valatask.outputs.append(d)
			valatask.deps_node = d

	if valatask.attr("install_path") and ('cshlib' in features or 'cstlib' in features):
		headers_list = [o for o in valatask.outputs if o.suffix() == ".h"]
		self.install_vheader = []
		for header in headers_list:
			top_src = self.bld.srcnode
			package = self.env['PACKAGE']
			try:
				api_version = Utils.g_module.API_VERSION
			except AttributeError:
				version = Utils.g_module.VERSION.split(".")
				if version[0] == "0":
					api_version = "0." + version[1]
				else:
					api_version = version[0] + ".0"
			install_path = '${INCLUDEDIR}/%s-%s/%s' % (package, api_version, header.path_from(top_src))
			self.install_vheader.append(self.bld.install_as(install_path, header, self.env))

		vapi_list = [o for o in valatask.outputs if (o.suffix() in (".vapi", ".deps"))]
		self.install_vapi = self.bld.install_files('${DATAROOTDIR}/vala/vapi', vapi_list, self.env)

		gir_list = [o for o in valatask.outputs if o.suffix() == ".gir"]
		self.install_gir = self.bld.install_files('${DATAROOTDIR}/gir-1.0', gir_list, self.env)

valac_task = Task.update_outputs(valac_task) # no decorators for python2 classes

def configure(self):
	min_version = (0, 8, 0)
	min_version_str = "%d.%d.%d" % min_version

	valac = self.find_program('valac', var='VALAC')

	if not self.env["HAVE_GOBJECT"]:
		pkg_args = {'package':      'gobject-2.0',
			'uselib_store': 'GOBJECT',
			'args':         '--cflags --libs'}
		if getattr(Options.options, 'vala_target_glib', None):
			pkg_args['atleast_version'] = Options.options.vala_target_glib
		self.check_cfg(**pkg_args)

	if not self.env["HAVE_GTHREAD"]:
		pkg_args = {'package':      'gthread-2.0',
			'uselib_store': 'GTHREAD',
			'args':         '--cflags --libs'}
		if getattr(Options.options, 'vala_target_glib', None):
			pkg_args['atleast_version'] = Options.options.vala_target_glib
		self.check_cfg(**pkg_args)

	try:
		output = self.cmd_and_log(valac + " --version")
		version = output.split(' ', 1)[-1].strip().split(".")[0:3]
		version = [int(x) for x in version]
		valac_version = tuple(version)
	except Exception:
		valac_version = (0, 0, 0)

	self.msg('Checking for valac version >= ' + min_version_str, "%d.%d.%d" % valac_version, valac_version >= min_version)

	if valac_version < min_version:
		self.fatal("the valac version %r is too old (%r)" % (valac_version, min_version))

	self.env.VALAC_VERSION = valac_version
	self.env.VALAFLAGS     = []

def options (opt):
	valaopts = opt.add_option_group('Vala Compiler Options')
	valaopts.add_option ('--vala-target-glib', default=None,
		dest='vala_target_glib', metavar='MAJOR.MINOR',
		help='Target version of glib for Vala GObject code generation')
