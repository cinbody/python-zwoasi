#!/usr/bin/env python3
#
#/usr/bin/env python
#/usr/bin/env python2
#/usr/bin/env python3
#/cygdrive/c/apps_x64/Python36/python.exe
#	NOTE: The above version of python IS NOT CYGWIN's version. See comments below.
#
#	NOTE: change "python3" above to "python2" or "python" (/usr/bin/env )
#	to use a different interpreter.
#
#
#	Python wrapper for the ZWO ASI drivers by Steve Marple:
#		https://github.com/stevemarple/python-zwoasi
#
#	pip2 search zwoasi
#	pip2 install zwoasi
#	to install on Cygwin's v2.7 python
#
#	pip3 search zwoasi
#	pip3 install zwoasi
#	to install on Cygwin's v3.6 python
#
#
#	To use his examples and code, one must d/l the ZWO ASI SDK from:
#		https://astronomy-imaging-camera.com/software/
#	In this case:
#		ASI_Windows_SDK_V1.13.0.10
#	and supply the path to the 64 bit version 2 dll:
#		$ ./zwoasi_demo.py "./ASI_Windows_SDK_V1.13.0.10/ASI SDK/lib/x64/ASICamera2.dll"
#
#	zwo_command.py is based on Steve's zwoasi_demo.py
#
#	Started by using Cygwin's v2.7 python
#
#	Switched to python 3.6 to gain access to "allow_abbrev=False"
#
#
#	TODO:
#
#		load settings
#


import argparse
import os
import sys
import time
import zwoasi as asi

import re
import datetime
from collections import defaultdict
import ctypes as c
from itertools import repeat


__author__ = 'Chris Inbody'
__version__ = '0.0.15'
__license__ = 'MIT'


	#################################################
	#	Functions									#
	#################################################



#
#	Related to: C:\cygwin64\lib\python3.6\site-packages\zwoasi\__init__.py
#
#	Because "_ASI_CONTROL_CAPS", "get_control_values()", "_get_control_caps()" and "get_controls()"
#	return only '0' when polling my ASI174MM, I have to fix it here. I will have to map "{'Name': 'Exposure',.. "
#	to ".., 'ControlType': 0}" where I fix (overwrite with correct value) ControlType.
#	This is not likely the fault of \zwoasi\__init__.py or even zwolib, but more likely I have an
#	early version of the ASI174MM that did not implement modern API responses.
#
#	I may not have added all of these to the assignment as I was focused on the camera I have in hand
#
def remap_control_type(controls):

	ASI_GAIN = 0
	ASI_EXPOSURE = 1
	ASI_GAMMA = 2
	ASI_WB_R = 3
	ASI_WB_B = 4
	ASI_BRIGHTNESS = 5
	ASI_BANDWIDTHOVERLOAD = 6
	ASI_OVERCLOCK = 7
	ASI_TEMPERATURE = 8  # return 10*temperature
	ASI_FLIP = 9
	ASI_AUTO_MAX_GAIN = 10
	ASI_AUTO_MAX_EXP = 11
	ASI_AUTO_MAX_BRIGHTNESS = 12
	ASI_HARDWARE_BIN = 13
	ASI_HIGH_SPEED_MODE = 14
	ASI_COOLER_POWER_PERC = 15
	ASI_TARGET_TEMP = 16  # not need *10
	ASI_COOLER_ON = 17
	ASI_MONO_BIN = 18  # lead to less grid at software bin mode for color camera
	ASI_FAN_ON = 19
	ASI_PATTERN_ADJUST = 20

	for cn in controls:
		if cn in 'AutoExpMaxBrightness':
			controls[cn]['ControlType'] = ASI_AUTO_MAX_BRIGHTNESS
		if cn in 'AutoExpMaxExp':
			controls[cn]['ControlType'] = ASI_AUTO_MAX_EXP
		if cn in 'AutoExpMaxGain':
			controls[cn]['ControlType'] = ASI_AUTO_MAX_GAIN
		if cn in 'BandWidth':
			controls[cn]['ControlType'] = ASI_BANDWIDTHOVERLOAD
		if cn in 'Brightness':
			controls[cn]['ControlType'] = ASI_BRIGHTNESS
		if cn in 'Exposure':
			controls[cn]['ControlType'] = ASI_EXPOSURE
		if cn in 'Flip':
			controls[cn]['ControlType'] = ASI_FLIP
		if cn in 'Gain':
			controls[cn]['ControlType'] = ASI_GAIN
		if cn in 'Gamma':
			controls[cn]['ControlType'] = ASI_GAMMA
		if cn in 'HighSpeedMode':
			controls[cn]['ControlType'] = ASI_HIGH_SPEED_MODE
		if cn in 'Temperature':
			controls[cn]['ControlType'] = ASI_TEMPERATURE

	return controls



def save_control_values(filename, settings):

	with open(filename, 'w') as f:
		for k in sorted(settings.keys()):
			f.write('%s: %s\n' % (k, str(settings[k])))
	print('Camera settings saved to %s' % filename)





#
#	validate_args()
#
#	Based on the keys that parser.parse_args() returns (aka 'dest')
#	The list for each tested key is made of all other keys either that are either in conflict with
#	or required by the tested key.
#
#	required_deps = {'tested key' : ['required_1', 'required_2',...]}
#
def validate_args(args):

	required_deps =	{
					'image' :					[ 'camera_id' ],
					'get_controls' :			[ 'camera_id' ],
					'get_properties' :			[ 'camera_id' ],
					'get_control_values' :		[ 'camera_id' ],
					}

	conflict_deps =	{
					}

	for option in required_deps:
		if args[option]:
			for item in required_deps[option]:
				if args[item] is None:
					print ("\nRequired option: ", required_deps[option], " not present.\n")
					sys.exit(1)

	for option in conflict_deps:
		if args[option]:
			for item in required_deps[option]:
				if args[item] is not None:
					print ("\nConflicting option: ", required_deps[option], " present.\n")
					sys.exit(1)

	return




#
#	date_name()
#
#	add a "unique" identifier to filename
#
def date_name(filename):

	basename, file_extension = os.path.splitext(filename)
	the_middle = datetime.datetime.now().strftime("%y%m%d_%H%M%f")
	output_filename = "_".join([basename, the_middle]) + file_extension

	return output_filename


#
#	replacement help output
#
#	This relies a private part of the parser and may therefore
#	break in the future ([parser]._optionals._actions)
#
#	Argparses help output is kind of cluttered to me and while you can
#	work around most of the issues, there were a few left that I could not fix without
#	going into private space (ie argparse's incosistent printing of short option spacing).
#	See get_option_set() for additional details.
#
def help(parser, option_set):

	actions = parser._optionals._actions

	print()
	parser.print_usage()
	print()
	print (parser.description)
	print()

	output_str = ' '.ljust(80)

	print ("Options:")
	print()
	for an_action in actions:
		for strg in an_action.option_strings:
			if re.match ('(-{1})([a-z0-9]{1,2})', strg):
				output_str = output_str [:2] + strg + output_str[2+len(strg):]
			if re.match ('(-{2})([a-z0-9])', strg):
				output_str = output_str [:10] + strg + output_str[len(strg):]
		if an_action.help:
				output_str = output_str [:35] + an_action.help

		print (output_str)
		output_str = ' '.ljust(80)

	if option_set['help']['long_given']:
		print()
		print (parser.epilog)



#
#
#	This relies a private part of the parser and may therefore
#	break in the future ([parser]._optionals._actions)
#
#	Bottom line purpose of this func is to provide access to
#	the data struct created by all the "parser.add_argument()" calls
#
#	One thing this does aside from repackaging "parser._optionals._actions"
#	is to seperate out the "long" and "short" options, useful if there
#	are subtle differences to be handled (ie. --help vs -h to provide a more
#	detailed help message)
#
#	Another reason this was written was to provide access to the option's
#	'const' value, which argparse does not supply. For the use case in this app,
#	'const' is really being used as the 'default'. Whereas argparse only provides
#	access to the value of 'default'
#
#	The use of "defaultdict(dict)" here precludes the need to
#	initialize the dictionary, it figures out and backfills the
#	higher indexes on its own (in the case "an_action.dest"
#	
#	Switched to python 3.6 to gain access to:
#
#			argparse.ArgumentParser(	description='Process and save images from a camera',
#										allow_abbrev=False)
#
#		this is intended to minimize ambiguity issues.
#
#
#	Also, this allows me to bounce against argv and determine which options were set by the user
#	on the command line.
#
#	option_set[an_action.dest]['const']
#	option_set[an_action.dest]['help']
#	option_set[an_action.dest]['default']
#	option_set[an_action.dest]['short']
#	option_set[an_action.dest]['short_given']
#	option_set[an_action.dest]['long']
#	option_set[an_action.dest]['long_given']
#	option_set[an_action.dest]['arg_given']		This tells us an argument was supplied to a flagged option
#
def get_option_set(parser, argv):

	actions = parser._optionals._actions

	option_set = defaultdict(dict)
	
	for an_action in actions:
		option_set[an_action.dest]['const'] = an_action.const
		option_set[an_action.dest]['help'] = an_action.help
		option_set[an_action.dest]['default'] = an_action.default
		option_set[an_action.dest]['arg_given'] = ''

			#	Below we look for whether or not short and long options were
			#	initialized using "parser.add_argument()" calls.
			#	Also wik, if they were we check argv for their existence on the command line.
			#	Also, also wik,.. we look to see if a non-option argument (ie a filename, etc)
			#	was supplied after them.

		for strg in an_action.option_strings:
			if re.match ('(-{1})([a-z0-9]{1,2})', strg):
				option_set[an_action.dest]['short'] = strg
				if strg in argv:
						#	We look at the next argument to see if it's a not flag option
					if argv.index(strg) < len(argv) - 1:
						if not re.match ('(-{1,2})([a-z0-9])', argv[argv.index(strg) + 1]):
							option_set[an_action.dest]['arg_given'] = argv[argv.index(strg) + 1]
					option_set[an_action.dest]['short_given'] = True
				else:
					option_set[an_action.dest]['short_given'] = False
			if re.match ('(-{2})([a-z0-9])', strg):
				option_set[an_action.dest]['long'] = strg
				if strg in argv:
						#	We look at the next argument to see if it's a not flag option
					if argv.index(strg) < len(argv) - 1:
						if not re.match ('(-{1,2})([a-z0-9])', argv[argv.index(strg) + 1]):
							option_set[an_action.dest]['arg_given'] = argv[argv.index(strg) + 1]
					option_set[an_action.dest]['long_given'] = True
				else:
					option_set[an_action.dest]['long_given'] = False

	return option_set








#
#	main()
#


epilog_text = "Format: prog_name followed by [(long or short)option][argument]\n"
epilog_text += "\n"
epilog_text += "Some options have hard coded defaults whether or not you supply them.\n"
epilog_text += "Some options will use defaults only if you supply the option sans argument.\n"
epilog_text += "They can also take an argument which will then override the default.\n"
epilog_text += "These latter variety are a kind of \"flag or argument\" option in that if\n"
epilog_text += "these are not supplied in one or the other form, the function is disabled.\n"
epilog_text += "These are marked by an \'*\'.\n"
epilog_text += "\n"
epilog_text += "Examples:\n"
epilog_text += "  prog_name.py with no options: the default for the --image option is ignored.\n"
epilog_text += "  prog_name.py --image but no argument: the default for the --image option is used.\n"
epilog_text += "  prog_name.py --image <filename>: the default for the --image option is replaced with <filename>.\n"



parser = argparse.ArgumentParser(	description='Process and save images from a camera',
									epilog=epilog_text,
									allow_abbrev=False,
									add_help=False)



#
#	The following setup allows a kind of 3-way logic:
#
#		parser.add_argument(	'-i',
#								'--image',
#								default=None,	
#								metavar='',
#								const='output.jpg',
#								nargs='?',
#								help='Take one image, optinally stored in [filename]')
#
#	Default is set to None, nargs is set to '?' and a "backup default" is set using 'const'
#	
#	From the docs:
#
#		When add_argument() is called with option strings (like -f or --foo) and nargs='?'.
#		This creates an optional argument that can be followed by zero or one command-line arguments.
#		When parsing the command line, if the option string is encountered with no command-line argument
#		following it, the value of const will be assumed instead. See the nargs description for examples.
#
#	If the user supplies an argument, the option will be "not None" and therefore detectable
#	and we can check for options that either will not work together or will not work
#	without one another ( see validate_args() )
#
#	The end game for this was not obvious to me (this is the way I would like argparse
#	or any option parser to work),... If the user supplies no option a default
#	can be set by the program but we still know "no option" was supplied.
#	If the user supplies only the option (ie --save_settings with no arg)
#	we can tell that and use the default we have internally. If the user supplies
#	the arg, then we use that vs default => a kind of 3-way logic.
#
#	If you setup parser.add_argument() with just a default and don't use nargs and const
#	this way (and this is what I did initially), argparse will choke if the user supplies
#	an option without an arg.
#




parser.add_argument(	'-z',
						'--zwolib',
						default='./ASI_Windows_SDK_V1.13.0.10/ASI SDK/lib/x64/ASICamera2.dll',
						metavar='',
						help='ZWO ASI SDK library path (ASICamera2.dll)')
parser.add_argument(	'-l',
						'--list',
						default=None,
						action="store_true",
						help='List connected camera ids')
parser.add_argument(	'-c',
						'--camera_id',
						type=int,
						default=None,
						metavar='',
						help='Camera id to interface with, see -l/list')
parser.add_argument(	'-r',
						'--roi',
						type=int,
						default=None,
						nargs=4,
						metavar='',
						help='Set ROI [start x][start y][width][height]')
parser.add_argument(	'-g',
						'--gain',
						type=int,
						default=260,
						metavar='',
						help='Camera gain')
parser.add_argument(	'-o',
						'--offset',
						type=int,
						default=50,
						metavar='',
						help='Camera offset (aka brightness)')
parser.add_argument(	'-e',
						'--exposure',
						type=int,
						default=83000,
						metavar='',
						help='Camera exposure in us')
parser.add_argument(	'-gc',
						'--get_controls',
						default=None,
						action="store_true",
						help='List connected camera capabilities')
parser.add_argument(	'-gv',
						'--get_control_values',
						default=None,
						action="store_true",
						help='List connected camera capability value')
parser.add_argument(	'-gp',
						'--get_properties',
						default=None,
						action="store_true",
						help='List connected camera properties')
parser.add_argument(	'--save_settings',
						default=None,
						const="./settings.txt",
						nargs='?',
						metavar='',
						help='* Filename to save settings to (ascii text)')
parser.add_argument(	'--load_settings',
						default=None,
						const="./settings.txt",
						nargs='?',
						metavar='',
						help='* Filename to load settings from (ascii text)')
parser.add_argument(	'-i',
						'--image',
						default=None,	
						metavar='',
						const='./output.jpg',
						nargs='?',
						help='* Take one image, stored in [optional filename]')
parser.add_argument(	'-h',
						'--help',
						default=None,
						action="store_true",
						help='This message. --help = more details')

args = parser.parse_args()

option_set = get_option_set(parser, sys.argv)


if not len(sys.argv) > 1:
	help (parser, option_set)
	sys.exit(1)

if args.help:
	help (parser, option_set)
	sys.exit(1)



	#	At this point we can test for which args have been suppied by the user
	#	and check for compatibility with each other, 
validate_args(vars(args))





					# Initialize zwoasi with the name of the SDK library
if args.zwolib:
	asi.init(args.zwolib)
else:
	print('The path to the ZWO ASI SDK library is required (ASICamera2.dll)')
	sys.exit(1)


num_cameras = asi.get_num_cameras()

if num_cameras == 0:
	print('No cameras found')
	sys.exit(0)

if (args.camera_id is not None):
	if (args.camera_id > num_cameras - 1):
		print('Invalid camera selected')
		sys.exit(0)
	camera = asi.Camera(args.camera_id)
	camera_info = camera.get_camera_property()


cameras_found = asi.list_cameras()  # Models names of the connected cameras

	#	We pull 'controls' into main() so we can re-map (due to bad camera data)
	#	and use in overloaded get_control_values()

controls = camera.get_controls()
controls = remap_control_type(controls)



	#	Set some sensible defaults. They will need adjusting depending upon
	#	the sensitivity, lens and lighting conditions used.
	#	These have yet to be implemented in argument form

camera.disable_dark_subtract()
camera.set_control_value(asi.ASI_WB_B, 99)
camera.set_control_value(asi.ASI_WB_R, 75)
camera.set_control_value(asi.ASI_GAMMA, 50)
camera.set_control_value(asi.ASI_FLIP, 0)
camera.set_control_value(asi.ASI_BANDWIDTHOVERLOAD, camera.get_controls()['BandWidth']['MinValue'])

	#	Other camera settings assigned here based on args or defaults

camera.set_control_value(asi.ASI_GAIN, args.gain)
camera.set_control_value(asi.ASI_EXPOSURE, args.exposure)
camera.set_control_value(asi.ASI_BRIGHTNESS, args.offset)

	#	If imaging,...

if args.image is not None:
	try:
		# Force any single exposure to be halted
		camera.stop_video_capture()
		camera.stop_exposure()
	except (KeyboardInterrupt, SystemExit):
		raise
	except:
		pass

	basename, file_extension = os.path.splitext(args.image)

	if re.search ('(jpg)|(jpeg)', file_extension):
		camera.set_image_type(asi.ASI_IMG_RAW8)
	elif re.search ('(tif)|(tiff)', file_extension):
		camera.set_image_type(asi.ASI_IMG_RAW16)
	else:
		print ('image extension not supported')
		sys.exit(0)

	if args.roi:
		camera.set_roi(args.roi[0], args.roi[1], args.roi[2], args.roi[3])

	if not option_set['image']['arg_given']:
		for i in repeat(None, 5):
			camera.capture(filename=date_name(args.image))
	else:
		camera.capture(filename=args.image)



	#
	#	Unsure as to why at this point but many of these properties are unreliable
	#	on my ASI174MM. It is an earlier version and this may be why, but perhaps they
	#	should not be used as a tool to identify what can be done with the camera.
	#	ie get_camera_property() returned 'IsColorCam': True, and I have a MM camera.
	#
	#	ZWO ASI175MM is 1936 x 1216,... get_camera_property() reported values: 1936 x 4294967298
	#
	#	remap_control_type(controls) and an overloaded camera.get_control_values(controls)
	#	are a direct result of some of this missing (from the camera hardware) data.
	#

if args.get_properties:
	print('')
	print('Camera properties:')
	props = camera.get_camera_property()
	for k, v in sorted(props.items()):
		print('    %s : %s' %(k, v))

if args.get_controls:
	print('')
	for cn in sorted(controls.keys()):
		print('    %s:' % cn)
		for k in sorted(controls[cn].keys()):
			print('        %s: %s' % (k, repr(controls[cn][k])))

if args.list:
	print('Found %d cameras' % num_cameras)
	for n in range(num_cameras):
		print('    %d: %s' % (n, cameras_found[n]))

if args.get_control_values:
	for k in sorted(camera.get_control_values(controls).keys()):
		print('%s: %s' % (k, str(camera.get_control_values(controls)[k])))

if args.save_settings:
	save_control_values(args.save_settings, camera.get_control_values(controls))

































