import itertools
import os
import shutil
import sys
import tempfile
import traceback
import warnings
import logging
import wx
import wx.html

from Util.LoggingApplication import LoggingWXApp as App
from PMFServer.gui.ErrorConsole import ErrorDialogManager
from PMFServer.gui.GroupPanel import ResourcePanel
from PMFServer.gui.HTMLHelpFile import ScenarioHelpFileCreator
from PMFServer.gui.RelationshipPanel import RelationshipMatrixPanel, GroupRelationshipPanel
from PMFServer.gui.StatePanel import StatePanel
from PMFServer.gui.StringFormatting import getDefaultNumericDisplayPrecision, setDefaultNumericDisplayPrecision
from PMFServer.gui.widgets.Busy import BusyCursor
from PMFServer.gui.widgets.labels import makePMFHeading
from PMFServer.PerceptionModel import PerceptionModel
from PMFServer.PMFLibrary import PMFLibrary, PMFLibraryNameConflictException
from PMFServer.Relationship import RelationshipMatrix
from PMFServer.resources import getTransparentwxBitmap
from PMFServer.DecisionModel import ScriptedDecisionModel
from Util.Build import OperatingFromABuild
from StateSim.IDE.FactionSimDecisionModelGUI import COADecisionModelPanel
from StateSim.IDE.GeographyGUI import GeographicalResourceDistributionModelPanel
from StateSim.IDE.InstitutionGUI import RegionalInstitutionPanel,RegionlessInstitutionPanel
from StateSim.Models.Geography import GeographicalResourceDistributionModel
from StateSim.Models.InstitutionalModels import InstitutionModel
from StateSim.Models.Utilities import isInstitution,isLeader
from StateSim.Models.FactionSimDecisionModel import COADecisionModel,AuxiliaryCOADecisionModel
from StateSim.Viewer.gui.ExternalInfluence import isExternalInfluenceAgent
from StateSim.Viewer.gui.HTMLHelpFile import COAActionHelpFileCreator
from StateSim.Viewer.gui.StateSimAboutBox import StateSimAboutBox
from StateSim.Viewer.COAConfig import COAConfig
from StateSim.Models.Register import registerStateSimModels

class COAToolFrame(wx.Frame):
    """
    Main frame for the COA Tool.
    """

    ID_EXIT                 = wx.NewId()

    ID_FILE_LOAD            = wx.NewId()
    ID_FILE_SAVE            = wx.NewId()
    ID_FILE_SAVE_AS         = wx.NewId()
    ID_FILE_SAVE_CONFIG     = wx.NewId()
    ID_FILE_LOAD_CONFIG     = wx.NewId()

    ID_VIEW_PRECISION       = wx.NewId()

    ID_HELP_ABOUT           = wx.NewId()
    ID_HELP_HELP            = wx.NewId()

    def __init__(self, parent=None, id=-1, title="COA Tool", pos=wx.DefaultPosition, size=wx.Size(1000, 700), style=wx.DEFAULT_FRAME_STYLE, servFileName=None, scenarioName=None, configName=None):
        """
        Initialize the COA Tool frame.
        @param parent: parent window
        @type parent: wx.Window
        @param id: frame id
        @type id: int
        @param title: frame title
        @type title: basestring
        @param pos: frame position
        @type pos: wx.Point
        @param size: frame size
        @type size: wx.Size
        @param style: frame style
        @type style: int
        @param servFileName: serv file name
        @type servFileName: basestring
        @param scenarioName: scenario name
        @type scenarioName: basestring
        """
        super(COAToolFrame, self).__init__(parent, id, title, pos, size, style)
        self._title =   title
        wx.FileSystem.AddHandler(wx.ZipFSHandler())

        self.SetIcon(wx.IconFromBitmap(getTransparentwxBitmap("icons/pmf_server.ico")))

        self._library = PMFLibrary()
        self._library.bind(self._library.LoadDBEvent, self._onLoadServFile)
        self._library.bind(self._library.ClearDBEvent, self._onClearServFile)
        self._library.bind(self._library.SaveScenarioEvent, self._onSaveScenario)

        self._tempDir = tempfile.mkdtemp(prefix="COATool_")

        self._actionHelpFileCreator   = COAActionHelpFileCreator(self._library)
        self._actionHelpFilename      = "ActionHelp.htb"
        self._scenarioHelpFileCreator = ScenarioHelpFileCreator(self._library)
        self._scenarioHelpFilename    = "ScenarioHelp.htb"

        self._modified = False

        wx.EVT_CLOSE(self, self._onClose)

        # Menu bar

        self._fileMenu = wx.Menu()
        self._fileMenu.Append(self.ID_FILE_LOAD, "&Open Library\tCtrl+O", "Open a StateSim library from a serv file")
        self._fileMenu.Append(self.ID_FILE_SAVE, "&Save Library\tCtrl+S", "Save the current StateSim library to a serv file")
        self._fileMenu.Append(self.ID_FILE_SAVE_AS, "Save Library &As...\tCtrl+Alt+S", "Save the current StateSim library to a new serv file")
        self._fileMenu.AppendSeparator()
        self._fileMenu.Append(self.ID_EXIT, "E&xit\tCtrl+Q")
        self._fileMenu.Enable(self.ID_FILE_SAVE, False)
        self._fileMenu.Enable(self.ID_FILE_SAVE_AS, False)
        wx.EVT_MENU(self, self.ID_FILE_LOAD, self._onOpenLibrary)
        wx.EVT_MENU(self, self.ID_FILE_SAVE, self._onSaveLibrary)
        wx.EVT_MENU(self, self.ID_FILE_SAVE_AS, self._onSaveLibraryAs)
        wx.EVT_MENU(self, self.ID_EXIT, self._onExit)
        wx.EVT_MENU(self, self.ID_FILE_SAVE_CONFIG, self._onSaveConfig)
        wx.EVT_MENU(self, self.ID_FILE_LOAD_CONFIG, self._onLoadConfig)

        self._configMenu= wx.Menu()

        self._configMenu.Append(self.ID_FILE_LOAD_CONFIG, "&Load Config", "Save the current COA as a config independent of serv file")
        self._configMenu.Append(self.ID_FILE_SAVE_CONFIG, "&Save Config", "Save the current COA as a config independent of serv file")
        self._configMenu.Enable(self.ID_FILE_SAVE_CONFIG, False)



        self._viewMenu = wx.Menu()
        self._viewMenu.Append(self.ID_VIEW_PRECISION, "Set &Numeric Precision", "Set the display precision for numbers")
        wx.EVT_MENU(self, self.ID_VIEW_PRECISION, self._onChangeNumericPrecision)

        self._helpMenu = wx.Menu()
        self._helpMenu.Append(self.ID_HELP_HELP, "&Help\tF1")
        self._helpMenu.AppendSeparator()
        self._helpMenu.Append(self.ID_HELP_ABOUT, "&About StateSim")
        wx.EVT_MENU(self, self.ID_HELP_HELP, self._onHelp)
        wx.EVT_MENU(self, self.ID_HELP_ABOUT, self._onAbout)

        self._menuBar = wx.MenuBar()
        self._menuBar.Append(self._fileMenu, "&File")
        self._menuBar.Append(self._configMenu,"&Config")
        self._menuBar.Append(self._viewMenu, "&View")
        self._menuBar.Append(self._helpMenu, "&Help")

        self.SetMenuBar(self._menuBar)

        self._panel = COAToolPanel(self, self._library, servFileName=servFileName, scenarioName=scenarioName, configName=configName)

    # Callbacks

    def _onAbout(self, event):
        """
        Callback for selecting About StateSim from the Help menu.
        @param event: menu event
        @type event: wx.Event
        """
        StateSimAboutBox(self, imagePath="images/StateSimAbout.jpg")

    def _onChangeNumericPrecision(self, event):
        """
        Callback for selecting Set Numeric Precision from the View
        menu.
        @param event: menu event
        @type event: wx.Event
        """
        precision = wx.GetNumberFromUser("Select display precision", "Digits:", caption="Numeric Display Precision", value=getDefaultNumericDisplayPrecision(), min=1, max=sys.float_info.dig, parent=self)
        if precision != -1:
            setDefaultNumericDisplayPrecision(precision)

    def _onClearServFile(self, event):
        """
        Callback for a library being cleared.
        @param event: clear library event
        @type event: L{PMFServer.PMFLibrary.PMFLibrary.ClearDBEvent}
        """
        self._clearActionHelp()
        self._clearScenarioHelp()

    def _onClose(self, event):
        """
        Callback for window close event.
        @param event: close event
        @type event: wx.Event
        """
        self._panel.querySaveScript()
        self._panel.querySaveScenario()
        self.querySaveLibrary()
        if os.path.exists(self._tempDir):
            try:
                shutil.rmtree(self._tempDir)
            except Exception:
                if __debug__:
                    warnings.warn("Could not delete temporary directory: %s" % self._tempDir, RuntimeWarning)
        self.Destroy()

    def _onExit(self, event):
        """
        Callback for selecting Exit from the File menu.
        @param event: menu event
        @type event: wx.Event
        """
        self.Close(True)

    def _onHelp(self, event):
        """
        Callback for selecting Help from the Help menu.
        @param event: menu event
        @type event: wx.Event
        """
        helpCtrl = wx.html.HtmlHelpController(wx.html.HF_TOOLBAR | wx.html.HF_CONTENTS | wx.html.HF_SEARCH | wx.html.HF_DIALOG | wx.html.HF_MODAL, self)
        helpCtrl.SetTempDir(self._tempDir)
        helpCtrl.AddBook(os.path.join("help", "COATool.hhp"))
        actionHelp = os.path.join(self._tempDir, self._actionHelpFilename)
        if os.path.exists(actionHelp):
            helpCtrl.AddBook(actionHelp)
        scenarioHelp = os.path.join(self._tempDir, self._scenarioHelpFilename)
        if os.path.exists(scenarioHelp):
            helpCtrl.AddBook(scenarioHelp)
        helpCtrl.DisplayContents()
        helpCtrl.Destroy()

    def _onLoadServFile(self, event):
        """
        Callback for a serv file being loaded.
        @param event: serv file load event
        @type event: L{PMFServer.PMFLibrary.PMFLibrary.LoadDBEvent}
        """
        self._fileMenu.Enable(self.ID_FILE_SAVE, True)
        self._fileMenu.Enable(self.ID_FILE_SAVE_AS, True)
        self._configMenu.Enable(self.ID_FILE_SAVE_CONFIG, True)
        self._createActionHelp()
        self._createScenarioHelp()

    def _onOpenLibrary(self, event):
        """
        Callback for selecting Open Library from the File menu.
        @param event: menu event
        @type event: wx.Event
        """
        filename = self._getServFileNameFromUser("Open StateSim serv file")
        if filename:
            self._loadServFile(filename)

    def _onSaveLibrary(self, event):
        """
        Callback for selecting Save Library from the File menu.
        @param event: menu event
        @type event: wx.Event
        """
        servFileName = self._panel.getServFileName()
        if servFileName is None:
            filename = self._getServFileNameFromUser("Save as", flags=wx.FD_SAVE)
        else:
            filename = servFileName
        if filename:
            self._saveServFile(filename)

    def _onSaveLibraryAs(self, event):
        """
        Callback for selecting Save Library As from the File menu.
        @param event: menu event
        @type event: wx.Event
        """
        filename = self._getServFileNameFromUser("Save as", flags=wx.FD_SAVE)
        if filename:
            self._saveServFile(filename)

    def _onSaveConfig(self, event):
        """
        Callback for selecting Save Config from the File menu.
        @param event: menu event
        @type event: wx.Event
        """
        filename = self._getConfigFileNameFromUser("Config", flags=wx.FD_SAVE)
        if filename:
            self._panel.querySaveScript()
            self._panel.querySaveScenario()
            self._saveConfigFile(filename)

    def _onLoadConfig(self,event):
        filename = self._getConfigFileNameFromUser("Config", flags=wx.FD_OPEN)
        if filename:
            self._loadConfigFile(filename)

        #dlg = wx.MessageDialog(None, 'Not Yet Implemented', 'Nope', wx.OK | wx.ICON_INFORMATION)
        #dlg.ShowModal()
        #dlg.Destroy()
        
    def _onSaveScenario(self, event):
        """
        Callback for a save scenario event.
        @param event: save scenario event
        @type event: L{PMFServer.PMFLibrary.PMFLibrary.SaveScenarioEvent}
        """
        self._noteModification()

    # Modifications

    def isModified(self):
        """
        Return whether there are unsaved modifications to the library.
        @return: modified status
        @rtype: bool
        """
        return self._modified

    def querySaveLibrary(self):
        """
        If there are modifications, ask the user whether to save the
        library.
        """
        if self.isModified() and (wx.MessageBox("Library is modified. Save?", "COA Tool", wx.YES_NO) == wx.YES):
            self._saveServFile(self._panel.getServFileName())

    def _noteModification(self):
        """
        Note that there are unsaved modifications in the library.
        """
        self._modified = True

    def _clearModification(self):
        """
        Clear any modification notes.
        """
        self._modified = False

    # User utilities

    def _getConfigFileNameFromUser(self, message, flags=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST):
        """
        Get a config file name from the user.  Returns the filename if
        the user enters one and the empty string otherwise.
        @param message: message to display in the file dialog
        @type message: basestring
        @param flags: file dialog flags
        @type flags: int
        @return: serv file name (or the empty string, if the user does not enter one)
        @rtype: basestring
        """
        configFileName = self._panel.getConfigFileName()
        if configFileName is not None:
            defaultPath, defaultFilename = os.path.split(configFileName)
        else:
            defaultPath = os.path.join(os.getcwd())
            if not os.path.exists(defaultPath):
                defaultPath = os.getcwd()
            defaultFilename = ""
        return wx.FileSelector(message, defaultPath, defaultFilename, wildcard="config files (*.xml)|*.xml", flags=flags, parent=self)


    def _getServFileNameFromUser(self, message, flags=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST):
        """
        Get a serv file name from the user.  Returns the filename if
        the user enters one and the empty string otherwise.
        @param message: message to display in the file dialog
        @type message: basestring
        @param flags: file dialog flags
        @type flags: int
        @return: serv file name (or the empty string, if the user does not enter one)
        @rtype: basestring
        """
        servFileName = self._panel.getServFileName()
        if servFileName is not None:
            defaultPath, defaultFilename = os.path.split(servFileName)
        else:
            if OperatingFromABuild():
                defaultPath =   wx.GetApp().getUserPath()
            else:
                defaultPath = os.path.join(os.getcwd(), "serv")
                if not os.path.exists(defaultPath):
                    defaultPath = os.getcwd()
            defaultFilename = ""
        return wx.FileSelector(message, defaultPath, defaultFilename, wildcard="Serv files (*.xml,*.pickle)|*.xml;*.pickle", flags=flags, parent=self)

    # Library utilities

    def _loadServFile(self, filename):
        """
        Load the named serv file.
        @param filename: serv file name
        @type filename: basestring
        @return: whether the load was successful
        @rtype: bool
        """
        success = self._panel.loadServFile(filename)
        self._clearModification()
        return success

    def _saveServFile(self, filename):
        """
        Save the current library to a serv file.
        @param filename: file name to save to
        @type filename: basestring
        @return: whether the save was successful
        @rtype: bool
        """
        success = self._panel.saveServFile(filename)
        if success:
            self._clearModification()
        return success

    def _saveConfigFile(self, filename):
        """
        Save the current library to a config file.
        @param filename: file name to save to
        @type filename: basestring
        @return: whether the save was successful
        @rtype: bool
        """
        success = self._panel.saveConfigFile(filename)
        if success:
            self._clearModification()
        return success

    def _loadConfigFile(self, filename):
        """
        Load a config file into the current library
        @param filename: file name to load from
        @type filename: basestring
        @return: whether the load was successful
        @rtype: bool
        """
        success = self._panel.loadConfigFile(filename)
        if success:
            self._clearModification()
        return success

    # Help utilities

    def _createActionHelp(self):
        """
        Create help files for actions in the current library.
        """
        self._actionHelpFileCreator("Actions", intro="Help for actions available in the current library.", filename=self._actionHelpFilename, directory=self._tempDir)

    def _clearActionHelp(self):
        """
        Create any action help files.
        """
        self._removeHelpFile(self._actionHelpFilename)

    def _createScenarioHelp(self):
        """
        Create help files for scenarios in the current library.
        """
        self._scenarioHelpFileCreator("Scenarios", intro="Help for scenarios available in the current library.", filename=self._scenarioHelpFilename, directory=self._tempDir)

    def _clearScenarioHelp(self):
        """
        Clear any scenario help files.
        """
        self._removeHelpFile(self._scenarioHelpFilename)

    def _removeHelpFile(self, filename):
        """
        Remove the named help file, if it exists.  Note that this
        ignores all exceptions raised during the removal attempt.
        @param filename: help file name
        @type filename: basestring
        """
        path = os.path.join(self._tempDir, filename)
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                if __debug__:
                    warnings.warn("Could not remove help file: %s" % path, RuntimeWarning)


class COAToolPanel(wx.Panel):
    """
    Main panel for the COA tool.
    """

    def __init__(self, parent, library, style=wx.BORDER_STATIC, servFileName=None, scenarioName=None, configName=None):
        """
        Initialize the COA tool panel.
        @param parent: parent window
        @type parent: wx.Window
        @param library: current library
        @type library: L{PMFServer.PMFLibrary.PMFLibrary}
        @param style: panel style
        @type style: int
        @param servFileName: serv file name
        @type servFileName: basestring
        @param scenarioName: scenario name
        @type scenarioName: basestring
        """
        super(COAToolPanel, self).__init__(parent, style=style)

        self._library           = library
        self._agent             = None
        self._servFileName      = None
        self._scenarioName      = None
        self._modified          = False
        self._configFileName    = None

        self._scenarioChoice = wx.Choice(self)
        self._scenarioChoice.Enable(False)
        wx.EVT_CHOICE(self, self._scenarioChoice.GetId(), self._onScenarioSelect)

        self._agentChoice = wx.Choice(self)
        self._agentChoice.Enable(False)
        wx.EVT_CHOICE(self, self._agentChoice.GetId(), self._onAgentSelect)

        self._notebook = wx.Notebook(self)

        self._decisionPanel = COADecisionModelPanel(self._notebook, None, self._library)
        self._scenarioPanel = COAToolScenarioPanel(self._notebook, self._library)

        self._notebook.AddPage(self._decisionPanel, "Course of Action")
        self._notebook.AddPage(self._scenarioPanel, "Scenario")
        self._notebook.Enable(False)

        self._saveScenarioButton  = wx.Button(self, wx.ID_SAVE, "Save Scenario")
        self._saveScenarioButton.SetToolTipString("Save changes to the current scenario")
        self._saveScenarioButton.Enable(False)
        wx.EVT_BUTTON(self, self._saveScenarioButton.GetId(), self._onScenarioSave)

        buttonSizer = wx.StdDialogButtonSizer()
        buttonSizer.AddButton(self._saveScenarioButton)
        buttonSizer.Realize()

        sizerBorder = 5
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(wx.StaticText(self, -1, "Scenario:"), 0, wx.EXPAND | wx.ALL, sizerBorder)
        sizer.Add(self._scenarioChoice, 1, wx.EXPAND | wx.ALL, sizerBorder)
        sizer.Add(wx.StaticText(self, -1, "Leader:"), 0, wx.EXPAND | wx.ALL, sizerBorder)
        sizer.Add(self._agentChoice, 1, wx.EXPAND | wx.ALL, sizerBorder)
        sizer.Add(self._notebook, 15, wx.EXPAND | wx.ALL, sizerBorder)
        sizer.Add(buttonSizer, 0, wx.SHAPED | wx.ALIGN_CENTER, sizerBorder)
        sizer.AddSpacer(5)
        self.SetSizer(sizer)

        if servFileName is not None:
            if scenarioName is None:
                stepCount = 1
            else:
                stepCount = 2
            with BusyCursor():
                dlg = wx.ProgressDialog("Loading", "Please wait while library loads", stepCount)
                try:
                    success = self.loadServFile(servFileName)
                    dlg.Update(1)
                    if success and (scenarioName is not None):
                        self._loadScenario(scenarioName)
                        dlg.Update(2)
                finally:
                    dlg.Destroy()
        if configName is not None:
            self.loadConfigFile(configName)
        self.SetFocus()


    # Callbacks

    def _bindAgentCallbacks(self, agent):
        """
        Bind callbacks for agent.
        @param agent: agent
        @type agent: L{PMFServer.Agent.Agent}
        """
        decisionModel = agent.getModel(COADecisionModel)
        decisionModel.bind(decisionModel.ScriptEvent, self._onUpdateDecisionModel)
        decisionModel.bind(decisionModel.ChangeActiveScriptEvent, self._onUpdateDecisionModel)

    def _unbindAgentCallbacks(self, agent):
        """
        Unbind callbacks for agent.
        @param agent: agent
        @type agent: L{PMFServer.Agent.Agent}
        """
        agent.getModel(COADecisionModel).unbindObj(self)

    def _onAgentSelect(self, event):
        """
        Callback for selecting an agent from the external agent choice.
        @param event: choice event
        @type event: wx.Event
        """
        logging.info("onAgentSelect")
        self.querySaveScript()
        if self._agent is not None:
            self._unbindAgentCallbacks(self._agent)
        self._agent = self._library.getCurrentScenario().getAgentByName(self._agentChoice.GetStringSelection(), errorOnFailure=True)
        if self._agent.getModel(COADecisionModel) is None:
            self._agent.addModel(AuxiliaryCOADecisionModel)
            self._noteModification()
        logging.info("\tself._agent [%s] model [%s]" % (self._agent,self._agent.getModel(COADecisionModel)))
        self._bindAgentCallbacks(self._agent)
        self._decisionPanel.reinitialize(self._agent.getModel(COADecisionModel))
        self._scenarioPanel.reinitialize(self._agent)
        self._decisionPanel.Layout()
        self._notebook.Enable(self._agent is not None)

    def _onScenarioSave(self, event):
        """
        Callback for selecting the Save button.
        @param event: button event
        @type event: wx.Event
        """
        self._saveScenario()

    def _onScenarioSelect(self, event):
        """
        Callback for selecting a scenario from the scenario radio box.
        @param event: radio box event
        @type event: wx.Event
        """
        if self._scenarioChoice.GetStringSelection() != "<Select Scenario>":
            self._loadScenario(self._scenarioChoice.GetStringSelection())
        
        if self._scenarioChoice.GetString(0) == "<Select Scenario>":
            self._scenarioChoice.Delete(0)

    def _onUpdateDecisionModel(self, event):
        """
        Callback for when an agent's decision model is updated.
        @param event: script update event
        @type event: L{PMFServer.DecisionModel.AutomatonDecisionModel.UpdateScriptEvent}
        """
        self._noteModification()

    # Displays

    def _updateAgentChoice(self):
        """
        Update the agent choice from the current scenario.
        """
        self._agentChoice.Clear()
        for agent in sorted(itertools.ifilter(isLeader, self._library.getCurrentScenario().iterAgents())):
            self._agentChoice.Append(agent.getName())
        self._agentChoice.Enable(self._scenarioName is not None)
        if self._agentChoice.GetCount() > 0:
            self._agentChoice.Select(0)
            self._onAgentSelect(None)

    def _updateScenarioChoice(self):
        """
        Update the scenario choice from the current library.
        """
        self._scenarioChoice.Clear()

        scenarios = sorted(self._library.getScenarios())
        if len(scenarios) > 0:
            self._scenarioChoice.Append("<Select Scenario>")
            self._scenarioChoice.SetStringSelection("<Select Scenario>")
        for scenario in scenarios:
            self._scenarioChoice.Append(scenario.getName())
        self._scenarioChoice.Enable(self._servFileName is not None)

    # Modifications

    def isModified(self):
        """
        Return whether there are unsaved modifications to the scenario.
        @return: modified status
        @rtype: bool
        """
        return self._modified

    def querySaveScenario(self):
        """
        If there are modifications, ask the user whether to save the
        current scenario.
        """
        if self.isModified() and (wx.MessageBox("Scenario '%s' is modified. Save?" % self._scenarioName, "COA Tool", wx.YES_NO) == wx.YES):
            self._saveScenario()

    def querySaveScript(self):
        """
        If there are modifications to the script, ask the user whether
        to save it.
        """
        self._decisionPanel.querySaveScript()

    def _noteModification(self):
        """
        Note that there are unsaved modifications in the panel.
        """
        self._modified = True
        self._saveScenarioButton.Enable(True)

    def _clearModification(self):
        """
        Clear any modification notes.
        """
        self._modified = False
        self._saveScenarioButton.Enable(False)

    # Library utilities

    def getConfigFileName(self):
        """
        Get the current config file name, if there is one.  Returns None
        otherwise.
        @return: current config file name
        @rtype: basestring or None
        """
        return self._configFileName

    def getServFileName(self):
        """
        Get the current serv file name, if there is one.  Returns None
        otherwise.
        @return: current serv file name
        @rtype: basestring or None
        """
        return self._servFileName

    def getScenarioName(self):
        """
        Get the current scenario name, if there is one.  Returns None
        otherwise.
        @return: current scenario name
        @rtype: basestring or None
        """
        return self._scenarioName

    def loadServFile(self, filename):
        """
        Load the named serv file.
        @param filename: serv file name
        @type filename: basestring
        @return: whether the load was successful
        @rtype: bool
        """
        if self._agent is not None:
            self._unbindAgentCallbacks(self._agent)
        self._agent        = None
        self._servFileName = None
        self._scenarioName = None
        filename = os.path.abspath(filename)
        try:
            with ErrorDialogManager("Error loading serv file %s" % filename):
                with BusyCursor():
                    self._library.loadDatabase(filename)
                    self.GetParent().SetTitle("%s - %s" % ("COATool",filename))

        except Exception:
            self._library.newDatabase()
            success = False
        else:
            self._servFileName = filename
            success = True
        self._clearModification()
        self._decisionPanel.reinitialize(None)
        self._scenarioPanel.reinitialize(None)
        self._updateScenarioChoice()
        self._updateAgentChoice()
        self._notebook.Enable(False)
        return success

    def saveConfigFile(self, filename):
        """
        Save the current config to an sml file.
        @param filename: file name to save to
        @type filename: basestring
        @return: whether the save was successful
        @rtype: bool
        """
        filename = os.path.abspath(filename)
        try:
            with ErrorDialogManager("Error saving config file to %s" % filename):
                with BusyCursor():
                    config  =   COAConfig()
                    config.fillFromLibrary(self._library)
                    COAConfig.saveConfig(filename,config)
                    newConfig   =   COAConfig.readConfig(filename)
                    newConfig.validateAgainstLibrary(self._library)


        except Exception as e:
            return False
        else:
            self._configFileName = filename
            return True


    def loadConfigFile(self, filename):
        """
        Load a config file into the current library
        @param filename: file name to load
        @type filename: basestring
        @return: whether the save was successful
        @rtype: bool
        """
        filename = os.path.abspath(filename)
        try:
            with ErrorDialogManager("Error loading config from file %s" % filename):
                with BusyCursor():
                    newConfig   =   COAConfig.readConfig(filename)
                    newConfig.validateAgainstLibrary(self._library)
                    newConfig.dumpToLibrary(self._library)
                    self._decisionPanel.reinitialize(self._agent.getModel(COADecisionModel))

        except Exception as e:
            return False
        else:
            self._configFileName = filename
            return True


    def saveServFile(self, filename):
        """
        Save the current library to a serv file.
        @param filename: file name to save to
        @type filename: basestring
        @return: whether the save was successful
        @rtype: bool
        """
        filename = os.path.abspath(filename)
        try:
            with ErrorDialogManager("Error saving serv file to %s" % filename):
                with BusyCursor():
                    self._library.saveDatabase(filename)
        except Exception as e:
            return False
        else:
            self._servFileName = filename
            return True

    def _loadScenario(self, scenarioName):
        """
        Load the named scenario.
        @param scenarioName: scenario name
        @type scenarioName: basestring
        @return: whether the load was successful
        @rtype: bool
        """
        self.querySaveScript()
        self.querySaveScenario()
        try:
            with ErrorDialogManager("Error loading scenario %s." % scenarioName, library=self._library):
                with BusyCursor():
                    self._library.loadScenario(scenarioName)
        except Exception:
            return False
        else:
            if self._agent is not None:
                self._unbindAgentCallbacks(self._agent)
            self._agent = None
            self._scenarioName = scenarioName
            self._clearModification()
            self._scenarioChoice.SetStringSelection(self._scenarioName)
            self._decisionPanel.reinitialize(None)
            self._scenarioPanel.reinitialize(None)
            self._notebook.Enable(False)
            self._updateAgentChoice()
            return True

    def _saveScenario(self, scenarioName=None):
        """
        Save the current scenario.
        @param scenarioName: scenario name
        @type scenarioName: basestring
        """
        try:
            with ErrorDialogManager("Error saving scenario.", library=self._library):
                try:
                    with BusyCursor():
                        self._library.saveScenario(scenarioName)
                except PMFLibraryNameConflictException:
                    if wx.MessageBox("There is already a scenario named '%s'.  Would you like to overwrite it?", "Scenario Save", wx.YES_NO) == wx.YES:
                        with BusyCursor():
                            self._library.saveScenario(scenarioName, True)
        except Exception:
            pass
        else:
            self._clearModification()
            if scenarioName is not None:
                self._scenarioName = scenarioName


class COAToolScenarioPanel(wx.Panel):
    """
    Panel to display information about the scenario for the COA Tool.
    """

    def __init__(self, parent, library):
        """
        Initialize the panel.
        @param parent: parent window
        @type parent: wx.Window
        @param library: current library
        @type library: L{PMFServer.PMFLibrary.PMFLibrary}
        """
        super(COAToolScenarioPanel, self).__init__(parent)
        self._library = library
        self._agent   = None

        splitter = wx.SplitterWindow(self)
        splitter.SetMinimumPaneSize(1)

        self._perceivedCtrl = wx.TreeCtrl(splitter, style=wx.TR_HAS_BUTTONS | wx.TR_LINES_AT_ROOT | wx.TR_HIDE_ROOT | wx.TR_SINGLE)
        self._detailPanel   = wx.Panel(splitter)
        wx.EVT_TREE_SEL_CHANGED(self._perceivedCtrl, self._perceivedCtrl.GetId(), self._onPerceivedSelect)

        self._detailPanel.SetSizer(wx.BoxSizer(wx.VERTICAL))

        splitter.SplitVertically(self._perceivedCtrl, self._detailPanel, 250)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(splitter, 1, wx.EXPAND | wx.ALL, 2)
        self.SetSizer(sizer)

    def reinitialize(self, agent=None):
        """
        Reinitialize the panel.
        @param agent: agent to initialize the panel with
        @type agent: L{PMFServer.Agent.Agent}
        """
        self._perceivedCtrl.DeleteAllItems()
        self._detailPanel.GetSizer().Clear(True)
        self._agent = agent
        if (agent is not None) and agent.hasModel(PerceptionModel):
            self._fillPerceivedTree()

    def _fillPerceivedTree(self):
        """
        Fill the tree of perceived instances.
        """
        perceptionModel = self._agent.getModel(PerceptionModel)

        agents       = []
        groups       = []
        objects      = []
        institutions = []

        for perceived in sorted(perceptionModel.getPerceived()):
            if perceptionModel.getAffordedActions(perceived):
                if self._library.isEntityOfType(perceived, "Group"):
                    groups.append(perceived)
                elif isInstitution(perceived):
                    institutions.append(perceived)
                elif self._library.isEntityOfType(perceived, "Agent"):
                    agents.append(perceived)
                else:
                    objects.append(perceived)

        root = self._perceivedCtrl.AddRoot("Perceived")

        if agents:
            agentsNode = self._perceivedCtrl.AppendItem(root, "Agents")
            for agent in agents:
                item = self._perceivedCtrl.AppendItem(agentsNode, agent.getName())
                self._perceivedCtrl.SetPyData(item, (self._createAgentPage, agent))
            if not (groups or institutions):
                self._perceivedCtrl.Expand(agentsNode)

        if groups:
            groupsNode = self._perceivedCtrl.AppendItem(root, "Groups")
            for group in groups:
                item = self._perceivedCtrl.AppendItem(groupsNode, group.getName())
                self._perceivedCtrl.SetPyData(item, (self._createGroupPage, group))
            self._perceivedCtrl.Expand(groupsNode)

        if institutions:
            institutionsNode = self._perceivedCtrl.AppendItem(root, "Institutions")
            for institution in institutions:
                item = self._perceivedCtrl.AppendItem(institutionsNode, institution.getName())
                self._perceivedCtrl.SetPyData(item, (self._createInstitutionPage, institution))
            self._perceivedCtrl.Expand(institutionsNode)

        if objects:
            objectsNode = self._perceivedCtrl.AppendItem(root, "Objects")
            for obj in objects:
                item = self._perceivedCtrl.AppendItem(objectsNode, obj.getName())
                self._perceivedCtrl.SetPyData(item, (self._createObjectPage, obj))
            if not (agents or groups or institutions):
                self._perceivedCtrl.Expand(objectsNode)

    # Callbacks

    def _onPerceivedSelect(self, event):
        """
        Callback for selecting a perceivable from the perceived
        control.
        @param event: tree selection event
        @type event: wx.Event
        """
        self._detailPanel.GetSizer().Clear(True)
        data = self._perceivedCtrl.GetPyData(self._perceivedCtrl.GetSelection())
        if data is not None:
            creator, instance = data
            panel = creator(self._detailPanel, instance)
            self._detailPanel.GetSizer().Add(panel, 1, wx.EXPAND | wx.ALL, 2)
            self._detailPanel.Layout()

    # Detail Panel

    def _createAgentPage(self, parent, agent):
        """
        Create a page for agent.
        @param parent: parent window
        @type parent: wx.Window
        @param agent: agent
        @type agent: L{PMFServer.Agent.Agent}
        @return: page for agent
        @rtype: wx.Window or None
        """
        notebook = wx.Notebook(parent)
        notebook.AddPage(StatePanel(notebook, agent, self._library, True), "State")
        notebook.AddPage(RelationshipMatrixPanel(notebook, agent.getModel(RelationshipMatrix), self._library, True), "Relationships")
        return notebook

    def _createGroupPage(self, parent, group):
        """
        Create a page for group.
        @param parent: parent window
        @type parent: wx.Window
        @param group: group
        @type group: L{PMFServer.Group.Group}
        @return: page for group
        @rtype: wx.Window or None
        """
        notebook = wx.Notebook(parent)
        notebook.AddPage(StatePanel(notebook, group, self._library, True), "State")
        notebook.AddPage(ResourcePanel(notebook, self._library, group, readOnly=True), "Resources", True)
        if group.hasModel(GeographicalResourceDistributionModel):
            model = group.getModel(GeographicalResourceDistributionModel)
            notebook.AddPage(GeographicalResourceDistributionModelPanel(notebook, model, self._library, True), "Resources By Region")
        notebook.AddPage(GroupRelationshipPanel(notebook, self._library, group, readOnly=True), "Relationships")
        return notebook

    def _createInstitutionPage(self, parent, institution):
        """
        Create a page for institution.
        @param parent: parent window
        @type parent: wx.Window
        @param institution: institution
        @type institution: L{PMFServer.Agent.Agent}
        @return: page for institution
        @rtype: wx.Window or None
        """
        if isinstance( institution.getModel(InstitutionModel),RegionlessInstitutionPanel._MODEL_TYPE):
            return RegionlessInstitutionPanel(parent, institution.getModel(InstitutionModel), self._library, True)
        if isinstance( institution.getModel(InstitutionModel),RegionalInstitutionPanel._MODEL_TYPE):
            return RegionalInstitutionPanel(parent, institution.getModel(InstitutionModel), self._library, True)
        raise RuntimeError,"Invalid institution type [%s]" % institution.getModel(InstitutionModel)

    def _createObjectPage(self, obj):
        """
        Create a page for obj.
        @param parent: parent window
        @type parent: wx.Window
        @param obj: obj
        @type obj: L{PMFServer.Perceivable.Perceivable}
        @return: page for obj
        @rtype: wx.Window or None
        """
        return StatePanel(parent, obj, self._library, True)


def main():
    import optparse
    import sys

    
    logging.basicConfig(level=logging.INFO)
    logging.info("Initialized Logging")
    app =   App("StateSim Course of Action Tool")

    parser = app.getOptionParser()
    parser.add_option("-l", "--library", action="store", type="string", dest="library", help="serv file")
    parser.add_option("-s", "--scenario", action="store", type="string", dest="scenario", help="scenario name")
    parser.add_option("-c", "--config", action="store", type="string", dest="config", help="coa config to load")

    options, args = app.parseOptions()

    """
    argCount = len(args)
    if argCount == 1:
        library  = None
        scenario = None
    elif argCount == 2:
        library  = args[1]
        scenario = None
    elif argCount == 3:
        library  = args[1]
        scenario = args[2]
    else:
        parser.print_usage()
        sys.exit(1)
    """
    registerStateSimModels()
    app._useDefaultExceptHook()
    #Note - wxPython and Matplotlib have an initizliation issue on OSX, so handle it here.
    mainFrame   =   COAToolFrame( servFileName=options.library, scenarioName=options.scenario, configName=options.config)
    #mainFrame   =   MainFrame(options)
    mainFrame.Raise()
    app.go(mainFrame)

    #COATool(library, scenario).MainLoop()


if __name__ == "__main__":
    main()
