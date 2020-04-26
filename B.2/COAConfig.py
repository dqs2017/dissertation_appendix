import sys
import os
import itertools
import logging
import Util.XMLUtilities as XMLUtilities
from PMFServer.DecisionModel import ScriptedDecisionModel,DecisionModel
from PMFServer.Entity import NamedEntity
from StateSim.Models.Utilities import isExternalInfluenceAgent
from StateSim.Models.FactionSimDecisionModel import PsychSocialCOADecisionModel,COADecisionModel,AuxiliaryCOADecisionModel


class COADecision(object):
    def __init__(self):
        self.Action     =   None
        self.Target     =   None
        self.Params     =   {}

class COAParameter(object):
    def __init__(self):
        self.Name       =   None
        self.Value      =   None

class COATrigger(object):
    def __init__(self):
        self.Equation   =   None
        self.Kind       =   None
        self.Comp       =   None
        self.Value      =   None
        self.Parameters =   None
        self.Decisions  =   None

class COAStep(object):
    def __init__(self):
        self.Step       =   None
        self.Decisions  =   None
        #self.Index      =   None
        #self.Action     =   None
        #self.Target     =   None
        #self.Params     =   {}

class COAScript(object):
    def __init__(self):
        self.Name       =   None
        self.Cycle      =   False
        self.Active     =   False
        self.Steps      =   []
        self.Triggers   =   []

class COAAgent(object):
    def __init__(self):
        self.Name       =   None
        self.Scripts    =   []

class COAInstance(object):
    def __init_(self):
        self.Name       =   None

class COAConfig(object):

    def __init__(self):
        self.Library    =   None
        self.Scenario   =   None
        self.Agents     =   []

    def dumpToLibrary(self,library):
        calculator      =   library.getSimulation().getMetricsCalculator()
        scenario        =   library.getCurrentScenario()
        logging.info("Loading into Scenario [%s]" % scenario)
        for coaAgent in self.Agents:
            agent       =   scenario.getInstanceByName(coaAgent.Name,errorOnFailure=True)
            model       =   agent.getDecisionModel()
            #TODO - we might want more controlled behavior here, override vs auxiliery
            if not isinstance(agent.getDecisionModel(),ScriptedDecisionModel):
                agent.addModel(AuxiliaryCOADecisionModel)
                model   =   agent.getModel(AuxiliaryCOADecisionModel)

            logging.info("\tAgent [%s]" % agent)
            for coaScript in coaAgent.Scripts:
                script  =   []
                for idx in range(len(coaScript.Steps)):
                    step    =   []
                    for jdx in range(len(coaScript.Steps[idx].Decisions)):
                        coaDecision    =   coaScript.Steps[idx].Decisions[jdx]
                        action  =   library.getEntityByName(coaDecision.Action)
                        target  =   scenario.getInstanceByName(coaDecision.Target,errorOnFailure=True)
                        params  =   {}
                        for name in action.getParameterNames():
                            if name in ['actor','scenario','target','step']:
                                continue
                            if name not in coaDecision.Params:
                                raise RuntimeError,"Missing Decision Parameter [%s] for Action[%s]" % (name,action.getName())

                        for k,v in coaDecision.Params.iteritems():
                            if k not in action.getParameterNames():
                                raise ValueError,"No such Parameter [%s] on Action [%s]. Possible : [%s]" % (k,action.getName(),action.getParameterNames())
                            if isinstance(v,COAInstance):
                                params[k]   =   scenario.getInstanceByName(v.Name,errorOnFailure=True)
                            else:
                                params[k]   =   v
                        step.append( (action,target,params) )
                    script.append(step)

                triggers    =   []
                for idx in range(len(coaScript.Triggers)):
                    logging.info("Trigger [%s]" % idx)
                    coaTrigger  =   coaScript.Triggers[idx]
                    equName     =   coaTrigger.Equation
                    equ         =   calculator.getEquationSpec(equName)
                    logging.info("\tEquation [%s] Spec [%s]" % (equName,equ))
                    if equ is None:
                        raise RuntimeError,"No Such Equation [%s]" % equName
                    kind        =   coaTrigger.Kind
                    comp        =   coaTrigger.Comp
                    cmpValue    =   float(coaTrigger.Value)
                    paramDict   =   {}
                    for coaParameter in coaTrigger.Parameters:
                        spec    =   equ.getParameterSpec(coaParameter.Name)
                        if issubclass(spec.getKind(),NamedEntity):
                            value   =   scenario.getInstanceByName(coaParameter.Value,errorOnFailure=True)
                        else:
                            value   =   coaParameter.Value
                        paramDict[coaParameter.Name]    =   value
                    tparams   =   []
                    for name in paramDict.keys():
                        if name not in equ.getParameterNames():
                            raise RuntimeError,"Extranious Parameter [%s] from [%s]" % (name,equName)
                    for name in equ.getParameterNames():
                        if name not in paramDict:
                            if name == equ.TIME_PARAM:
                                value   =   't'
                            else:
                                raise RuntimeError,"Missing Trigger Parameter [%s] from [%s]" % (name,equName)
                        else:
                            value   =   paramDict[name]
                        tparams.append(tuple([name,value]))
                    logging.info("\tParams : %s" % str(tparams))
                    decisions   =   []
                    for jdx in range(len(coaScript.Triggers[idx].Decisions)):
                        coaDecision    =   coaScript.Triggers[idx].Decisions[jdx]
                        action  =   library.getEntityByName(coaDecision.Action)
                        target  =   scenario.getInstanceByName(coaDecision.Target,errorOnFailure=True)
                        dparams  =   {}
                        for name in action.getParameterNames():
                            if name in ['actor','scenario','target','step']:
                                continue
                            if name not in coaDecision.Params:
                                raise RuntimeError,"Missing Decision Parameter [%s] for Action [%s] in Trigger [%s]" % (name,action.getName(),equName)

                        for k,v in coaDecision.Params.iteritems():
                            if isinstance(v,COAInstance):
                                dparams[k]   =   scenario.getInstanceByName(v.Name,errorOnFailure=True)
                            else:
                                dparams[k]   =   v
                        decisions.append( (action,target,dparams) )
                        logging.info("\tDecision : %s" % (str(decisions[-1])))
                    triggers.append( tuple([  tuple([equName,kind,comp,cmpValue,tparams]) ,tuple(decisions)  ]) )
                model.setScript(coaScript.Name,script,triggers,coaScript.Cycle,coaScript.Active)

    def fillFromLibrary(self,library):
        self.Agents     =   []
        for agent in library.getCurrentScenario().iterAgents():
            model       =   agent.getModel(COADecisionModel)
            if model is None:
                continue
            if len(model.getScriptNames()) == 0:
                continue
            self.Agents.append(COAAgent())
            self.Agents[-1].Name    =   agent.getName()
            for scriptName in model.iterScriptNames():
                coaScript           =   COAScript()
                coaScript.Name      =   scriptName
                coaScript.Cycle     =   (model.cycles(scriptName))
                coaScript.Active    =   model.isActiveScript(scriptName)
                script              =   model.getScript(scriptName)
                
                for step, decisionSpecs in enumerate(script):
                    coaScript.Steps.append(COAStep())
                    coaScript.Steps[-1].Step        =   step
                    coaScript.Steps[-1].Decisions   =   []
                    for (action, target, params) in decisionSpecs:
                        coaScript.Steps[-1].Decisions.append(COADecision())
                        coaScript.Steps[-1].Decisions[-1].Action  =   action.getName()
                        coaScript.Steps[-1].Decisions[-1].Target  =   target.getName()
                        coaScript.Steps[-1].Decisions[-1].Params  =   {}
                        for k,v in params.iteritems():
                            if isinstance(v,NamedEntity):
                                coaScript.Steps[-1].Decisions[-1].Params[k]       =   COAInstance()
                                coaScript.Steps[-1].Decisions[-1].Params[k].Name  =   v.getName()
                            else:
                                coaScript.Steps[-1].Decisions[-1].Params[k]       =   v
                
                for (triggerSpec,decisionSpecs) in  model.getTriggers(scriptName):
                    (equName,kindName,compName,value,params) =    triggerSpec
                    coaTrigger              =   COATrigger()
                    coaTrigger.Equation     =   equName
                    coaTrigger.Kind         =   kindName
                    coaTrigger.Comp         =   compName
                    coaTrigger.Value        =   value
                    coaTrigger.Parameters   =   []
                    for (name,value) in params:
                        coaTrigger.Parameters.append(COAParameter())
                        coaTrigger.Parameters[-1].Name              =   name
                        if isinstance(value,NamedEntity):
                            coaTrigger.Parameters[-1].Value         =   value.getName()
                        else:
                            coaTrigger.Parameters[-1].Value         =   value
                    coaTrigger.Decisions  =   []
                    for (action, target, params) in decisionSpecs:
                        coaTrigger.Decisions.append(COADecision())
                        coaTrigger.Decisions[-1].Action =   action.getName()
                        coaTrigger.Decisions[-1].Target =   target.getName()
                        coaTrigger.Decisions[-1].Params =   {}
                        for k,v in params.iteritems():
                            if isinstance(v,NamedEntity):
                                coaTrigger.Decisions[-1].Params[k]       =   COAInstance()
                                coaTrigger.Decisions[-1].Params[k].Name  =   v.getName()
                            else:
                                coaTrigger.Decisions[-1].Params[k]       =   v
                    coaScript.Triggers.append(coaTrigger)              
                self.Agents[-1].Scripts.append(coaScript)
        
    def validateAgainstLibrary(self,library):
        scenario    =   library.getCurrentScenario()
        logging.info("Vadlidating Against [%s] : [%s]" % (library,scenario))
        for agent in self.Agents:
            if agent.Name not in [x.getName() for x in scenario.getAgents()]:
                raise RuntimeError,"Invalid COA for agent [%s], no such agent" % (agent.Name)
            logging.info("\tAgent [%s]" % agent.Name)
            for script in agent.Scripts:
                for step in script.Steps:
                    for decision in step.Decisions:
                        if decision.Action not in [x.getName() for x in library.getActions()]:
                            raise RuntimeError,"Invalid COA for agent [%s], no such action [%s] in library" % (agent.Name,decision.Action)
                        if decision.Target not in scenario.getInstanceNames():
                            raise RuntimeError,"Invalid COA for agent [%s], no such target [%s] in scenario" % (agent.Name,decision.Target)

    @staticmethod
    def saveConfig(file_name,config):
        XMLUtilities.writeXMLToFile(config,file_name,writer=COAConfigWriter(COAConfig))

    @staticmethod
    def readConfig(file_name):
        return XMLUtilities.readXMLFromFile(file_name,COAConfigReader(COAConfig))
#-----------------------------------------------------------------------------------------------
class COAConfigReader(XMLUtilities.XMLReader):
    def __init__(self,imp):
        super(COAConfigReader,self).__init__()


        self._registerNodeName("Config","_createConfigFromNode")
        self._registerNodeName("Leader","_createAgentFromNode")
        self._registerNodeName("Script","_createScriptFromNode")
        self._registerNodeName("Decision","_createDecisionFromNode")
        self._registerNodeName("Step","_createStepFromNode")
        self._registerNodeName("Parameter","_createParameterFromNode")
        self._registerNodeName("Trigger","_createTriggerFromNode")
        self._registerNodeName("Instance","_createInstanceFromNode")

        self._registerNodeName("COAConfig","_createCOAConfigFromNode")
        self._registerNodeName("COAScript","_createCOAScriptFromNode")
        self._registerNodeName("COAStep","_createCOAStepFromNode")
        self._registerNodeName("COAAgent","_createCOAAgentFromNode")
        self._registerNodeName("COAInstance","_createCOAInstanceFromNode")

    def _createAgentFromNode(self,node):
        rv          =   COAAgent()
        rv.Name     =   node._attributes["Name"]
        rv.Scripts  =   []
        for child in node.iterChildren():
            if isinstance(child,COAScript):
                rv.Scripts.append(child)
        return rv

    def _createDecisionFromNode(self,node):
        rv          =   COADecision()
        rv.Action   =   node._attributes["Action"]
        rv.Target   =   node._attributes["Target"]
        for child in node.iterChildren():
            if isinstance(child, XMLUtilities.TaggedObject):
                setattr(rv, child.tag, child.object)        
        return rv

    def _createStepFromNode(self,node):
        rv              =   COAStep()
        rv.Step         =   node._attributes["Value"]
        rv.Decisions    =   []
        for child in node.iterChildren():
            if isinstance(child,COADecision):
                rv.Decisions.append(child)
        return rv

    def _createParameterFromNode(self,node):
        rv              =   COAParameter()
        rv.Name         =   node._attributes["Name"]
        rv.Value        =   node._attributes["Value"]
        return rv

    def _createTriggerFromNode(self,node):
        rv              =   COATrigger()
        rv.Equation     =   node._attributes["Equation"]
        rv.Kind         =   node._attributes["Kind"]
        rv.Comp         =   node._attributes["Comp"]
        rv.Value        =   node._attributes["Value"]
        rv.Decisions    =   []
        rv.Parameters   =   []
        for child in node.iterChildren():
            if isinstance(child,COADecision):
                rv.Decisions.append(child)
            if isinstance(child,COAParameter):
                rv.Parameters.append(child)
        return rv

    def _createScriptFromNode(self,node):
        rv              =   COAScript()
        rv.Name         =   node._attributes["Name"]
        rv.Cycle        =   node._attributes["Cycle"]
        rv.Active       =   node._attributes["Active"]
        rv.Steps        =   []
        rv.Triggers     =   []
        for child in node.iterChildren():
            if isinstance(child,COAStep):
                rv.Steps.append(child)
            if isinstance(child,COATrigger):
                rv.Triggers.append(child)
        return rv

    def _createConfigFromNode(self,node):
        rv              =   COAConfig()
        rv.Agents       =   []
        for child in node.iterChildren():
            if isinstance(child,COAAgent):
                rv.Agents.append(child)
        return rv

    def _createInstanceFromNode(self,node):
        rv          =   COAInstance()
        rv.Name     =   node._attributes["Name"]
        return rv
    #-------------------------------------------------------------------------------
    #   Legacy Readers
    #-------------------------------------------------------------------------------
    def _createCOAConfigFromNode(self,node):
        rv          =   COAConfig()
        for child in node.iterChildren():
            if isinstance(child, XMLUtilities.TaggedObject):
                setattr(rv, child.tag, child.object)        
        return rv

    def _createCOAAgentFromNode(self,node):
        logging.info("Loading Legacy Agent Node")
        rv          =   COAAgent()
        rv.Name     =   node._attributes["Name"]
        for child in node.iterChildren():
            if isinstance(child, XMLUtilities.TaggedObject):
                setattr(rv, child.tag, child.object)
        scripts =   []

        for script in rv.Scripts:
            logging.info("Script : %s" % script)
            coaScript           =   COAScript()
            coaScript.Name      =   script.Name
            coaScript.Steps     =   []
            steps               =   {}
            for step in script.Steps:
                if step.Step not in steps:
                    steps[step.Step]            =   COAStep()
                    steps[step.Step].Step       =   step.Step
                    steps[step.Step].Decisions  =   []
                steps[step.Step].Decisions.append(step)

            for key in sorted(steps.keys()):
                coaScript.Steps.append(steps[key])
            scripts.append(coaScript)
        rv.Scripts  =   scripts

        if "Active" in node._attributes:
            for script in rv.Scripts:
                if script.Name == node._attributes["Active"]:
                    script.Active = True
        logging.info("/Loading Legacy Agent Node")
        return rv

    def _createCOAInstanceFromNode(self,node):
        rv          =   COAInstance()
        rv.Name     =   node._attributes["Name"]
        return rv

    def _createCOAScriptFromNode(self,node):
        rv          =   COAScript()
        rv.Name     =   node._attributes["Name"]
        rv.Active   =   node._attributes.get("Active",False)
        rv.Cycle    =   eval(node._attributes["Cycle"])
        for child in node.iterChildren():
            if isinstance(child, XMLUtilities.TaggedObject):
                setattr(rv, child.tag, child.object)        
        return rv

    def _createCOAStepFromNode(self,node):
        rv          =   COAStep()
        rv.Index    =   int(node._attributes["Index"])
        rv.Step     =   int(node._attributes["Step"])
        rv.Action   =   node._attributes["Action"]
        rv.Target   =   node._attributes["Target"]
        for child in node.iterChildren():
            if isinstance(child, XMLUtilities.TaggedObject):
                setattr(rv, child.tag, child.object)        
        return rv

#-----------------------------------------------------------------------------------------------
class COAConfigWriter(XMLUtilities.XMLWriter):
    def __init__(self,imp):
        super(COAConfigWriter,self).__init__()
        self._registerObjectType(COAConfig, "_createCOAConfigNode")
        self._registerObjectType(COAScript, "_createCOAScriptNode")
        self._registerObjectType(COAStep, "_createCOAStepNode")
        self._registerObjectType(COAAgent, "_createCOAAgentNode")
        self._registerObjectType(COAInstance, "_createCOAInstanceNode")
        self._registerObjectType(COADecision,"_createCOADecisionNode")
        self._registerObjectType(COAParameter,"_createCOAParameterNode")
        self._registerObjectType(COATrigger,"_createCOATriggerNode")

    def _createCOAAgentNode(self,data,document):
        node = document.createElement("Leader")
        node.setAttribute("Name",str(data.Name))
        for script in data.Scripts:
            node.appendChild(self._createNode(script,document))
        return node

    def _createCOAConfigNode(self,data,document):
        node = document.createElement("Config")
        for agent in data.Agents:
            node.appendChild(self._createNode(agent,document))
        return node

    def _createCOAScriptNode(self,data,document):
        node = document.createElement("Script")
        node.setAttribute("Name",str(data.Name))
        node.setAttribute("Cycle",str(data.Cycle))
        node.setAttribute("Active",str(data.Active))
        for step in data.Steps:
            node.appendChild(self._createNode(step,document))
        for trigger in data.Triggers:
            node.appendChild(self._createNode(trigger,document))
        return node

    def _createCOAStepNode(self,data,document):
        node = document.createElement("Step")
        node.setAttribute("Value",str(data.Step))
        for decision in data.Decisions:
            node.appendChild(self._createNode(decision,document))
        return node

    def _createCOATriggerNode(self,data,document):
        node = document.createElement("Trigger")
        node.setAttribute("Equation",data.Equation)
        node.setAttribute("Kind",data.Kind)
        node.setAttribute("Comp",data.Comp)
        node.setAttribute("Value",str(data.Value))
        for parameter in data.Parameters:
            node.appendChild(self._createNode(parameter,document))
        for decision in data.Decisions:
            node.appendChild(self._createNode(decision,document))
        return node

    def _createCOAParameterNode(self,data,document):
        node = document.createElement("Parameter")
        node.setAttribute("Name",str(data.Name))
        node.setAttribute("Value",str(data.Value))
        return node

    def _createCOADecisionNode(self,data,document):
        node = document.createElement("Decision")
        if data.Target is not None:
            node.setAttribute("Target",str(data.Target))
        if data.Action is not None:
            node.setAttribute("Action",str(data.Action))
        node.appendChild(self._createNode(data.Params,document,Tag="Params"))
        return node

    def _createCOAInstanceNode(self,data,document):
        node = document.createElement("Instance")
        node.setAttribute("Name",str(data.Name))
        return node
