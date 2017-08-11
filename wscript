#!/usr/bin/env python
'''This wscript file drives the WCT validation suite.

The validation suite is a number of "tasks" (in waf's definition)
connected by their input/output files thus forming a directed acyclic
graph.

Rules to add validtion tasks are:

1) The task MUST be reproducible by running commands outside of waf.

2) The task MUST assume the installed, user environment is set up (or
rely on WCT unit tests and libraries in the WCT "build" area).

2) The task MUST accept input/output file names on its command line
and not generate either internally.

'''

import os
from glob import glob

def options(opt):
    opt.load('md5_tstamp')
    
    opt = opt.add_option_group('WCT Validation Options')
    opt.add_option('--wct-build', type='string', default=None,
                   help="Include tests that rely on libs/execs in the WCT build directory.")
    opt.add_option('--wct-data', type='string', default=None,
                   help="Specify base for validation dataset.")
    pass




def configure(cfg):
    cfg.load('md5_tstamp')

    cfg.env.env = dict(os.environ)

    # needed to generate HTML.  "pip install yasha"
    cfg.find_program("yasha", var="YASHA", mandatory=True)

    wctbld = cfg.options.wct_build
    if (wctbld):

        ldpath = list()
        for subdir in glob(os.path.join(wctbld, "*")):
            for test in glob(os.path.join(subdir, "test_*")):
                if (os.path.isfile(test) and os.access(test, os.X_OK)):
                    name = os.path.basename(test)
                    cfg.find_program(test, var=name.upper(), mandatory=True)

            if glob(os.path.join(subdir, "*.so")):
                ldpath.append(subdir)

        oldldpath = cfg.env.env.get( 'LD_LIBRARY_PATH', None)
        cfg.env.env['LD_LIBRARY_PATH']  = ':'.join(ldpath)
        if oldldpath:
            cfg.env.env['LD_LIBRARY_PATH'] += ":" + oldldpath


    # find main WCT CLI
    cfg.find_program("wire-cell", var="WIRE_CELL", mandatory=True)

    # Make sure the wirecell-* python CLIs are available
    for pkg in "util sigproc gen validate".split():
        cli = "wirecell-" + pkg
        cfg.find_program(cli, var=cli.replace("-","_").upper(), mandatory=True)
        

    # See if we can run tests needing art.
    cfg.find_program("art", var="ART", uselib_store="ART", mandatory=False)

    datadir = cfg.options.wct_data
    if datadir is None:
        datadir = os.path.join(os.path.realpath("."), "data/validation")
    if not os.path.exists(datadir):
        raise ValueError("No such directory: %s" % datadir)
    cfg.env.DATADIR = datadir
        
    cfg.recurse('nfsp')
    pass



def build(bld):
    bld.load('md5_tstamp')

    #
    # some basic tests
    #

    bld(rule="${TEST_JSONNET} > ${TGT[0].abspath()} 2>&1", target="test_jsonnet.log")


    #
    # Tests that use art/larsoft.
    #
 
    magnify_files_from_art = list()

    bld(rule="(${ART} --version || true) > ${TGT[0].abspath()} 2>&1", target="art-version.txt")
    bld(rule="(${ART} --help || true) > ${TGT[0].abspath()} 2>&1", target="art-help.txt")
    bld(rule="(${ART} --print-description WCLS || true)  > ${TGT[0].abspath()} 2>&1 ", target="art-wcls-help.txt")
    bld(rule="grep -q 'tool_type: WCLS' ${SRC[0].abspath()} && touch ${TGT[0].abspath()}",
        source = "art-wcls-help.txt", target = "art-wcls-help.ok")

    bld.recurse('nfsp')

