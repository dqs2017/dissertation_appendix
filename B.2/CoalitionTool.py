import logging
import os
import sys
import time
from multiprocessing import Process


try:
    from Util.LoggingApplication import LoggingWXApp as App
    hasWX   =   True
except ImportError:
    from Util.LoggingConsoleApplication import LoggingConsoleApp as App
    hasWX   =   False

reload(sys)
sys.setdefaultencoding('utf-8')

def doRun(in_name):
    from StateSim.Viewer.gui.CoalitionTool.Simulator import getConfigGlob
    logging.basicConfig(level=logging.INFO)
    root,ext    =   os.path.splitext(in_name)
    outName     =   root + ".csv"
    logName     =   root + ".log"
    handler = logging.FileHandler(logName,"w", encoding=None, delay="false")
    handler.setLevel(logging.INFO)
    logging.getLogger().addHandler(handler)
    formatter = logging.Formatter("[%(filename)s:%(lineno)s:%(funcName)s() ] %(message)s")
    for handler in logging.getLogger().handlers:
        handler.setFormatter(formatter)


    if sys.version_info >= (2,7):
        logging.captureWarnings(True)
    logging.info("Starting Log [%s] PID [%d]" % (logName,os.getpid()))
    logging.info("[%s]=>[%s]" % (in_name,outName))
    logging.info("Loading Config File [%s]" % in_name)
    getConfigGlob().load(in_name)
    sim              =   getConfigGlob().makeSimulator()
    while sim.doStep():
        pass
    logging.info("Writing Data to [%s]" % outName)
    sim.saveData(outName)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = App("Coalition Simulator")
    parser  =   app.getOptionParser()
    parser.add_option('-b', '--batch', help="batch operation",action="store_true",default=False)
    parser.add_option('-o', '--output', help="Name of output file to create", type="string",default=None)
    parser.add_option('-i', '--input', help="Name of input file to load", type="string",default=None)
    parser.add_option('-a', '--auto' , help="Autorun on a directory of settings files", type="string",default=None)
    options,args = app.parseOptions()
    
    if options.auto:
        try:
            logging.info("Running in Auto Mode")
            from StateSim.Viewer.gui.CoalitionTool.Simulator import getConfigGlob
            import glob
            import gc
            if not os.path.exists(options.auto):
                logging.error("No such directory [%s]" % options.auto)
                sys.exit(0)

            threads =   []
            for inName in glob.glob(os.path.join(options.auto,"*.ini")):
                logging.info("inName  [%s] exists [%s]" % (inName,os.path.exists(inName)))
                threads.append(Process(target=doRun,args=(inName,)))

            for thread in threads:
                thread.start()

            for thread in threads:
                thread.join()

            """
            for inName in glob.glob(os.path.join(options.auto,"*.ini")):
                root,ext    =   os.path.splitext(inName)
                outName     =   root + ".csv"
                logging.info("[%s]=>[%s]" % (inName,outName))
                logging.info("Loading Config File [%s]" % inName)
                getConfigGlob().load(inName)
                sim              =   getConfigGlob().makeSimulator()
                while sim.doStep():
                    pass
                logging.info("Writing Data to [%s]" % outName)
                sim.saveData(outName)
                gc.collect()
            """
        except Exception:
            logging.exception("Caught Exception")
            raise


    elif options.batch:
        try:
            logging.info("Running in Batch Mode")
            from StateSim.Viewer.gui.CoalitionTool.Simulator import getConfigGlob
            if options.input is None:
                logging.error("Required Parameter [%s] missing" % "input")
                sys.exit(0)
            if options.output is None:
                logging.error("Required Parameter [%s] missing" % "output")
                sys.exit(0)

            logging.info("Loading Config File [%s]" % options.input)
            getConfigGlob().load(options.input)
            sim              =   getConfigGlob().makeSimulator()
            while sim.doStep():
                pass
            logging.info("Writing Data to [%s]" % options.output)
            sim.saveData(options.output)
        except Exception:
            logging.exception("Caught Exception")
            raise

    elif hasWX == False:
        logging.error("GUI mode requires wxPython")
    else:
        app._useDefaultExceptHook()
        #Note - wxPython and Matplotlib have an initizliation issue on OSX, so handle it here.
        from StateSim.Viewer.gui.CoalitionTool.MainFrame import MainFrame
        mainFrame   =   MainFrame(options)
        app.go(mainFrame)

