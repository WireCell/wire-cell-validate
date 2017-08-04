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
        
    pass


def build(bld):
    bld.load('md5_tstamp')

    #bld.add_group('group1')
    #bld.set_group('group1')

    datadir = bld.root.find_node(bld.env.DATADIR)
    print "data dir at " , datadir.abspath()
    
    bld.add_group('basic_tests')
    bld(rule="${TEST_JSONNET} > ${TGT[0].abspath()} 2>&1", target="test_jsonnet.log")


    # Tests that use WCT unit test programs.
    bld.add_group('unit_tests')
    te_pattern = "${TEST_EXAM_%s} ${SRC[0].abspath()} ${TGT[0].abspath()} > ${TGT[1].abspath()} 2>&1"
    mdcmd = "${WIRECELL_VALIDATE} magnify-diff -o ${TGT[0].abspath()} ${SRC[0].abspath()} ${SRC[1].abspath()}"
    mdcmd += " > ${TGT[1].abspath()} 2>&1"
    for filename in ["nsp_2D_display_3455_0_6.root", "nsp_2D_display_3493_821_41075.root"]:
        ref = datadir.find_node(filename)
        basename = filename.replace(".root","")

        for short_name, long_name, hist_name in [("tenf", "noise_filters", "raw"),
                                                 ("tesp", "signal_proc", "decon")]:
            boname = basename + "-" + short_name

            def rname(n): return "%s%d.root" % (boname, n)
            def lname(n): return "%s%d.log"  % (boname, n)

            tecmd = te_pattern % long_name.upper()
            bld(rule=tecmd, source=ref, target=[rname(1), lname(1)])
            bld(rule=tecmd, source=rname(1), target=[rname(2), lname(2)])
            bld(rule=tecmd, source=rname(2), target=[rname(3), lname(3)])

            def rdname(l): return "%s-diff%s.root" % (boname, l)
            def rlname(l): return "%s-diff%s.log"  % (boname, l)
            def rokname(l): return "%s-diff%s.ok"  % (boname, l)

            bld(rule=mdcmd, source=[ref, rname(1)],      target=[rdname("r1"), rlname("r1")])
            bld(rule=mdcmd, source=[rname(1), rname(2)], target=[rdname("12"), rlname("12")])
            bld(rule=mdcmd, source=[rname(2), rname(3)], target=[rdname("23"), rlname("23")])
                
            testcmd = 'test -z "$(grep _%s ${SRC[0].abspath()})" && touch ${TGT[0].abspath()}' % hist_name
            #bld(rule=testcmd, source=rlname("r1"), target=rokname("r1"))
            #bld(rule=testcmd, source=rlname("12"), target=rokname("12"))
            bld(rule=testcmd, source=rlname("23"), target=rokname("23"))


    # Tests that require a working larsoft environment
    bld.add_group('larsoft')

    bld(rule="(${ART} --version || true) > ${TGT[0].abspath()} 2>&1", target="art-version.txt")
    bld(rule="(${ART} --help || true) > ${TGT[0].abspath()} 2>&1", target="art-help.txt")
    bld(rule="(${ART} --print-description WCLS || true)  > ${TGT[0].abspath()} 2>&1 ", target="art-wcls-help.txt")
    bld(rule="grep 'tool_type: WCLS' ${SRC[0].abspath()} && touch ${TGT[0].abspath()}",
        source = "art-wcls-help.txt", target = "art-wcls-help.ok")

    art_cmd_pattern = "${ART} -n 1 -c %s -o ${TGT[0].abspath()} -s ${SRC[0].abspath()} > ${TGT[1].abspath()} 2>&1"

    for event in ["0005937-00027-01378"]:
        larsoft_filename = "larsoft-%s.root" % event
        rawnode = datadir.find_node(larsoft_filename)
        print "Using raw file input: %s " % rawnode.abspath()
        basename = larsoft_filename.replace(".root","")
        def oname(level, ext="root"): return "%s-%s.%s" % ( basename, level, ext)
        bld(rule=art_cmd_pattern % "uboone-nf-sp-mag.fcl",
            source = rawnode, target = [oname("nf-sp","root"), oname("nf-sp","log"), "magnify-nf-sp.root"])
        magnify_filename = "magnify-%s-nf-sp.root" % event
        bld(rule="cp ${SRC[0].abspath()} ${TGT[0].abspath()}",
            source="magnify-nf-sp.root", target=magnify_filename)

def garbage():

    top = vld.path.parent
    sm = top.children                     # submodules
    wire_cell = sm["apps"].find_or_declare("wire-cell"),
    # fixme: move any and all configs used for validation into this package
    bld.env.CFGDIR = sm["cfg"].abspath()

    bld(rule="${SRC[0].abspath()} --help > ${TGT[0].abspath()} 2>&1",
            source=wire_cell,
            target="help_output.txt")
    bld(rule="test $(wc -l < ${SRC} ) = 9 && touch ${TGT[0].abspath()}",
            source="help_output.txt",
            target="help_output.txt.ok")


    bld(rule="${JSONNET} -J ${CFGDIR} -o ${TGT[0].abspath()} ${SRC[0].abspath()}",
            source = sm["cfg"].find_resource("uboone/fourdee.jsonnet"),
            target = "uboone-fourdee.json")
