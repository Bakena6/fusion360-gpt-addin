
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
import hashlib

import base64
import functools

#from ... import config
from ...lib import fusion360utils as futil


def print(string):
    """redefine print for fusion env"""
    futil.log(str(string))

print(f"RELOADED: {__name__.split("%2F")[-1]}")


class ToolCollection:
    """
    methods colletion
    """

    #DEBUG = True
    #static

    #debug_print = True

    # store references to fusion object based on id
    log_results = True
    log_errors = True

    def tool_call(func):
        """
        Wraps fusion interface calls
        """
        # TODO probably a better way to select functions wrapped in this 
        func.__wrapper__ = "tool_call"

        # for retrieving wrapped function kwarg names
        @functools.wraps(func)
        def wrapper(self, *args, **kwds):
            self.app = adsk.core.Application.get()

            #print(f"Call: {func.__name__}")

            results = func(self, *args, **kwds)

            if getattr(ToolCollection, "log_results") == True:
                self.print_results(results)

            #print("func end")
            return results

        return wrapper

    def log_print(self, output):
        print(output)

    @classmethod
    def set_class_attr(cls, settings_dict):

        setting_name = settings_dict.get("setting_name")
        setting_val = settings_dict.get("setting_val")

        current_val = getattr(cls, setting_name, None)

        setattr(ToolCollection, setting_name, setting_val)
        print(f"{setting_name} set from {current_val} => {setting_val}")

    def print_results(self, results):

        if isinstance(results, str):
            try:
                formatted_results = json.dumps(json.loads(results), indent=4)
            except:
                formatted_results = results
        else:
            formatted_results = results

        print(formatted_results)

    def __init__(self, ent_dict):
        self.methods = self._get_methods()
        self.ent_dict = ent_dict
        #self.ent_dict = {}


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

    def _hash_string_to_fixed_length(self, input_string: str, length: int = 10) -> str:
        """
        Returns a stable, unique, alphanumeric hash string of the specified length
        for the given input_string. Uses SHA-256, then Base64, removing non-alphanumeric
        characters and truncating/padding as needed.

        :param input_string: The input string to hash.
        :param length: The desired length of the resulting hash (default=10).
        :return: A hash string of the given length (alphanumeric only).
        """
        # 1) Compute SHA-256 hash
        input_string = str(input_string)
        sha_hash = hashlib.sha256(str(input_string).encode('utf-8')).digest()

        # 2) Encode as Base64 (returns a bytes object)
        b64_encoded = base64.b64encode(sha_hash)  # e.g. b'abcd1234=='

        # Convert to ASCII string
        hash_str = b64_encoded.decode('ascii')  # e.g. "abcd1234=="

        # 3) Remove non-alphanumeric characters (like '=', '+', '/')
        hash_str = re.sub(r'[^A-Za-z0-9]', '', hash_str)

        # 4) Truncate or pad to desired length
        # If it's shorter than 'length' after removing symbols (rare), we can pad with '0'.
        if len(hash_str) < length:
            hash_str += '0' * (length - len(hash_str))
        else:
            hash_str = hash_str[:length]

        return hash_str

    def set_obj_hash(self, entity: object, token_str: str= None, length=5):
        """
        adds a fusion360 to the hash:object dict
        """
        entity_attrs = dir(entity)

        # if token_string passed in
        if token_str !=  None:
            token_str = str(token_str)
        else:
            for attr_name in ["entityToken", "name"]:
                if attr_name in entity_attrs:
                    try:
                        token_str = getattr(entity, attr_name, None)
                    except Exception as e:
                        print(e)
                        continue
                    if token_str != None:
                        break
                    else:
                        return

        #print(token_str)
        hash_val = self._hash_string_to_fixed_length(str(token_str), length)

        hash_val = f"__{hash_val}"


        self.ent_dict[hash_val] = entity

        return hash_val


    def get_hash_obj(self, hash_val):
        """
        adds a fusion360 to the hash:object dict
        """

        return self.ent_dict.get(hash_val)








