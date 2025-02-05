
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

import functools

#from ... import config
from ...lib import fusion360utils as futil


def print(string):
    """redefine print for fusion env"""
    futil.log(str(string))



class FusionSubmodule:
    """
    methods colletion
    """

    def __init__(self):
        print(f"FUSON SHARED RELOAD")
        self.methods = self._get_methods()
        self.ent_dict = {}

    def _get_methods(self):
        """
        creates list fusion interface functions
        """
        methods = {}

        for attr_name in dir(self):

            # ignore any method with leading underscore "_", e.g __init__, 
            # ignore functions that don't directly interface with fusion workspace
            if attr_name[0] == "_":
                continue

            attr = getattr(self, attr_name)

            if callable(attr) == False:
                continue

            if str(attr.__class__) == "<class 'method'>":
                methods[attr_name] = attr

        return methods

    def _find_component_by_name(self, component_name:str="comp1"):
        """
        called from methods, not Assistant directly
        """

        # Access the active design
        app = adsk.core.Application.get()
        design = adsk.fusion.Design.cast(app.activeProduct)
        rootComp = design.rootComponent

        if component_name == rootComp.name:
            return rootComp, None

        # Find the target component
        targetComponent = None
        for occ in rootComp.allOccurrences:
            if occ.component.name == component_name:
                targetComponent = occ.component
                break


        # return non errors when comp is found
        errors = None
        if not targetComponent:
            # include list of availble comp names
            componentNameList = set()
            componentNameList.add(rootComp.name)

            for occ in rootComp.allOccurrences:
                componentNameList.add(occ.component.name)

            errors =  f'Error: Component "{component_name}" not found. Available Components: \n{componentNameList}'


        return targetComponent, errors

    def _find_occurrence_by_name(self, occurrence_name: str="comp1:1"):
        """
        called from methods, not Assistant directly
        """

        # Access the active design
        app = adsk.core.Application.get()
        design = adsk.fusion.Design.cast(app.activeProduct)
        rootComp = design.rootComponent

        errors = None

        try:

            # Search all occurrences (including nested).
            targetOccurrence = None
            for occ in rootComp.allOccurrences:
                if occ.name == occurrence_name:
                    targetOccurrence = occ

            # check beck occ path
            if targetOccurrence is None:
                for occ in rootComp.allOccurrences:
                    if occ.fullPathName == occurrence_name:
                        targetOccurrence = occ

            if targetOccurrence is None:
                occ_parts = occurrence_name.split(":")
                occurrence_name = ''.join([ occ_parts[-2], ":", occ_parts[-1]])
                for occ in rootComp.allOccurrences:
                    if occ.name == occurrence_name:
                        targetOccurrence = occ

        except Exception as e:
            print(e)

        if not targetOccurrence:
            errors = f"Error: No occurrence found for '{occurrence_name}'."

        return targetOccurrence, errors

    def _find_sketch_by_name(self, component, sketch_name):
        """
        called from methods, not Assistant directly, selects sketch in component
        """
        # Find the target sketch
        targetSketch = None
        for sketch in component.sketches:
            if sketch.name == sketch_name:
                targetSketch = sketch
                break

        errors = None
        if not targetSketch:
            sketch_names = []
            for sketch in component.sketches:
                sketch_names.append(sketch.name)

            errors =  f'Error: Sketch "{sketch_name}" not found in component {component.name}. Available sketches in Component {component.name}: \n{sketch_names}'


        return targetSketch, errors

    def _find_body_by_name(self, component, body_name):
        """
        called from methods, not Assistant directly, selects sketch in component
        """
        body = None

        body_names = []
        for b in component.bRepBodies:
            body_names.append(b.name)
            if b.name == body_name:
                body = b
                break

        errors = None
        if not body:
            errors =  f'Error: Body "{body_name}" not found in component {component.name}. Available bodies in Component {component.name}: \n{body_names}'


        return body, errors

