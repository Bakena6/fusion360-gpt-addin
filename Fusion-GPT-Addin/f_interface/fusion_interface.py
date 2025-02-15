




import adsk.core
import adsk.fusion
#import adsk.cam
import traceback
import sys
import math
import os
import json
import inspect
import re

#from multiprocessing.connection import Client
from array import array
import time

import importlib
import functools

from .. import config
from ..lib import fusion360utils as futil

from . import modules
from .modules import cad_modeling, shared, transient_objects, document_data, utilities
from .modules.shared import ToolCollection

#print(modules)

#members = inspect.getmembers(modules)
#print(members)
#importlib.reload(modules)

def print(string):
    """redefine print for fusion env"""
    futil.log(str(string))


print(f"RELOADED: {__name__.split("%2F")[-1]}")

# send info to html palette
PALETTE_ID = config.palette_id
app = adsk.core.Application.get()
ui = app.userInterface
palette = ui.palettes.itemById(PALETTE_ID)

ent_dict = {}


class FusionInterface:
    """
    interface between Fusion360 api and OpenAI Assistant
    methonds in this class are made avilable to the OpenAI Assistants API
    via the GptClient class
    """

    def __init__(self, app, ui):
        self.app = app
        self.ui = ui
        self.design = adsk.fusion.Design.cast(self.app.activeProduct)

        ent_dict["design"] = self.design
        ent_dict["root"] = self.design.rootComponent

        # method collections
        self.submodules = [
            document_data.GetStateData(ent_dict),
            document_data.SetStateData(ent_dict),
            transient_objects.TransientObjects(ent_dict),
            cad_modeling.CreateObjects(ent_dict),
            utilities.Utilities(ent_dict),
            utilities.ImportExport(ent_dict),
            utilities.Joints(ent_dict),
            cad_modeling.ModifyObjects(ent_dict),
        ]

        fusion_methods = {}
        for submod in self.submodules:
            for method_name, method in submod.methods.items():
                # add method from container classes to main interface class
                setattr(self, method_name, method)

    # TODO do this without hard coading modules name
    def _reload_modules(self):
        importlib.reload(shared)
        importlib.reload(transient_objects)
        importlib.reload(document_data)
        importlib.reload(cad_modeling)
        importlib.reload(utilities)

    def update_settings(self, settings_dict ):
        ToolCollection.update(settings_dict)

    def get_tools(self):
        """
        creates list fusion interface functions
        """
        methods = {}

        # add modules and create methods
        for mod in self.submodules:
            class_name = mod.__class__.__name__

            # class name used for display
            methods[class_name] = {}

            for attr_name in dir(mod):

                attr = getattr(mod, attr_name)
                wrapper = getattr(attr, "__wrapper__", None )
                if wrapper != "tool_call":
                    continue

                if str(attr.__class__) == "<class 'method'>":
                    # method signature
                    sig = inspect.signature(attr)

                    attr = inspect.unwrap(attr)

                    default_vals = inspect.getfullargspec(attr).defaults

                    if default_vals != None:
                        n_default_vals = len(default_vals)
                    else:
                        n_default_vals = 0

                    param_dict = {}
                    for index, param_name in enumerate(sig.parameters):
                        annotation = sig.parameters.get(param_name).annotation

                        if index < n_default_vals:
                            default_val = default_vals[index]
                        else:
                            default_val = None

                        param_info_dict = {
                            "type": str(annotation),
                            "default_val": default_val
                        }

                        #param_info_dict
                        param_dict[param_name] = param_info_dict

                    methods[class_name][attr_name] = param_dict

        return methods


    def get_docstr(self):
        """
        creates list fusion interface functions
        """
        method_list = []
        for attr_name in dir(self):

            attr = getattr(self, attr_name)

            if callable(attr) == False:
                continue

            if str(attr.__class__) == "<class 'method'>":
                sig = inspect.signature(attr)

                wrapper = getattr(attr, "__wrapper__", None )

                if wrapper != "tool_call":
                    continue

                docstring = attr.__doc__

                print(attr_name)
                json_method = json.loads(docstring)

                method_list.append(json_method)


        method_list = json.dumps(method_list)
        self.tools_json = method_list
        return method_list

