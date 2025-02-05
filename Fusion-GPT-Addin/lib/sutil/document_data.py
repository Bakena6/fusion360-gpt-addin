# document data
#
#

import adsk.core
import adsk.fusion
import adsk.cam
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

import hashlib
import base64
import re

from ... import config
from ...lib import fusion360utils as futil

# send info to html palette
from .shared import FusionSubmodule

def print(string):
    """redefine print for fusion env"""
    futil.log(str(string))



class GetStateData(FusionSubmodule):
    """
    methods used by Realtime API to retrive state of Fusion document
    """


    def __init__(self):
        super().__init__()  # Call the base class constructor
        #self.ent_dict = {}

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
        sha_hash = hashlib.sha256(input_string.encode('utf-8')).digest()

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



    def _set_obj_hash(self, entityToken, entity, length=5):

        hash_val = self._hash_string_to_fixed_length(entityToken, length)

        hash_val = f"{entity.objectType.split(":")[-1]}__{hash_val}"

        self.ent_dict[hash_val] = entity

        return hash_val


    def _get_obj_hash(self, hash_val):
        return self.ent_dict[hash_val]




    def get_root_component_name(self):
        """
        {
            "name": "get_root_component_name",
            "description": "Retrieves the name of the root component in the current Fusion 360 design.",
            "parameters": {}
        }
        """
        try:
            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)

            # Access the active design
            if design:
                # Return the name of the root component
                return design.rootComponent.name
            else:
                return None

        except Exception as e:
            return None

    def _get_all_components(self) -> str:
        """
        {
          "name": "get_all_components",
          "description": "Retrieves all components in the current design and returns their basic information in a JSON array.",
          "parameters": {
            "type": "object",
            "properties": {
            },
            "required": [],
            "returns": {
              "type": "string",
              "description": "A JSON array of component info. Each item may include componentName, isRoot, and other metadata."
            }
          }
        }
        """

        try:
            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            design = adsk.fusion.Design.cast(product)

            # The design's 'allComponents' property retrieves every component in the design
            all_comps = design.allComponents
            comp_list = []

            for comp in all_comps:
                # Basic info about each component

                material_name = getattr(comp.material, "name", None)

                comp_data = {
                    "name": comp.name,
                    "material": material_name,
                    #"parentDesign": comp.parentDesign.rootComponent.name
                    # Add any additional info if needed
                }

                attr_list = [
                    "isBodiesFolderLightBulbOn",
                    "isCanvasFolderLightBulbOn",
                    "isConstructionFolderLightBulbOn",
                    "isDecalFolderLightBulbOn",
                    "isJointsFolderLightBulbOn",
                    "isSketchFolderLightBulbOn",
                    "description",
                    "entityToken"

                ]

                for attr in attr_list:
                    attr_val =  getattr(comp, attr, None)

                    if attr == "entityToken":
                        attr_val = self._set_obj_hash(comp.name, comp)

                    comp_data[attr] = attr_val

                # attributes that return iterables
                iter_attr_list = [
                    "occurrences",
                    "bRepBodies",
                    "sketches",
                    "jointOrigins",
                    "joints",
                    "modelParameters",
                ]

                for iter_attr in iter_attr_list:
                    attr_val =  getattr(comp, iter_attr, None)


                    if attr_val == None:
                        continue

                    if len(attr_val) == 0:
                        continue

                    name_list = [i.name for i in attr_val]
                    comp_data[iter_attr] = name_list

                comp_list.append(comp_data)


            root_comp = design.rootComponent
            root_comp_data = {
                "name": root_comp.name,
                "id": root_comp.id,
            }


            #return json.dumps(return_data, indent=4)
            #return json.dumps(return_data)
            return comp_list

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()

    def _get_ent_attrs(self, entity, attr_list):
        """
        get entity info
        """

        ent_info = { }
        for attr in attr_list:

            if "." in attr:

                attr0, attr1 = attr.split(".")

                sub_ent = getattr(entity, attr0, None)
                if sub_ent is None:
                    continue
                attr_val = getattr(sub_ent, attr1)
                ent_info[attr] = attr_val

            elif hasattr(entity, attr) == True:

                attr_val = getattr(entity, attr)

                if attr == "entityToken":
                    attr_val = self._set_obj_hash(attr_val, entity)

                ent_info[attr] = attr_val

        return ent_info

    def get_design_as_json(self, attributes_list=[]) -> str:
        """
            {
              "name": "get_design_as_json",
              "description": "Collects information about the active Fusion 360 design (including components, bodies, sketches, joints, and nested occurrences) and returns a JSON-encoded string describing the entire structure.",
              "parameters": {
                "type": "object",
                "properties": { },
                "required": [],
                "returns": {
                  "type": "string",
                  "description": "A JSON-encoded string representing the structure of the current design, including name, bodies, sketches, joints, and nested occurrences for each component."
                }
              }
            }
        """

        app = adsk.core.Application.get()
        ui = app.userInterface
        design = adsk.fusion.Design.cast(app.activeProduct)

        if not app:
            return "{}"  # Return empty JSON object if no Application is found

        product = app.activeProduct
        if not product or not isinstance(product, adsk.fusion.Design):
            return "{}"  # Return empty JSON object if no active design

        design = adsk.fusion.Design.cast(product)


        # Recursively gather data for each component
        def get_component_data(occ, component):

            object_types = [
                "bRepBodies",
            ]

            # entities in component
            occ_dict = {
                "associated_component": component.name,
            }

            # from root comp
            global_attrs = [
                "name",
                "entityToken",
                "objectType",
                "isLightBulbOn",
                "appearance.name",
                "isVisible",
                "isGrounded",
                "isReferencedComponent",
                "opacity"
            ]

            #occurrence_data = self._get_ent_attrs(occ, global_attrs)
            #comp_dict["occurrence_data"] = occurrence_data

            if occ != None:
                #print(occ.name)

                #occurrence level attributes
                ent_info = self._get_ent_attrs(occ, global_attrs)
                occ_dict.update(ent_info)

                # try theese attrbutes on multiple objects
                for object_name in object_types:

                    # body, joint, sketch etc
                    objectArray = getattr(occ, object_name)


                    for obj in objectArray:
                        #print(f"context: {obj.assemblyContext}")
                        ent_info = self._get_ent_attrs(obj, global_attrs)

                        if occ_dict.get(object_name) == None:
                            occ_dict[object_name] = []

                        occ_dict[object_name].append(ent_info)

            if occ == None:
                ent_list = enumerate(component.occurrences)
            else:
                ent_list = enumerate(occ.childOccurrences)

            for index, occ in ent_list:
                sub_comp = occ.component
                if sub_comp:
                    occ_data = get_component_data(occ, sub_comp)
                    object_type = "occurrences"
                    if occ_dict.get(object_type) == None:
                        occ_dict["occurrences"] = []
                    occ_dict["occurrences"].append(occ_data)


            return occ_dict


        # Build a dictionary that holds the entire design structure
        design_data = {
            "rootComponent_name": design.rootComponent.name,
            "components": self._get_all_components(),
            "occurrences": get_component_data(None, design.rootComponent)["occurrences"]
        }



        print(json.dumps(design_data, indent=4))
        # Convert dictionary to a JSON string with indentation
        return json.dumps(design_data)



    def set_entity_values(self, updates_list: list = [
        { "entityToken": " ", "attributeName": "isLightBulbOn", "attributeValue": True }
    ]) -> str:
        """
        {
          "name": "set_entity_values",
          "description": "Sets a single property on each referenced entity by token. Each update item has { 'entityToken': <string>, 'attributeName': <string>, 'attributeValue': <any> }. The function sets entity.<attributeName> = <attributeValue> if it is writable.",
          "parameters": {
            "type": "object",
            "properties": {
              "updates_list": {
                "type": "array",
                "description": "An array of update instructions. Each item: { 'entityToken': <string>, 'attributeName': <string>, 'attributeValue': <any> }.",
                "items": {
                  "type": "object",
                  "properties": {
                    "entityToken": { "type": "string" },
                    "attributeName": { "type": "string" },
                    "attributeValue": { "type": ["string","boolean","number"] }
                  },
                  "required": ["entityToken", "attributeName", "attributeValue"]
                }
              }
            },
            "required": ["updates_list"],
            "returns": {
              "type": "string",
              "description": "A JSON object mapping each entityToken to the final property value or null if an error occurred."
            }
          }
        }
        """

        #print(self.ent_dict.keys())
        try:
            if not updates_list or not isinstance(updates_list, list):
                return "Error: updates_list must be a non-empty list."

            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            design = adsk.fusion.Design.cast(product)

            # Final results mapped: token -> final value or None
            results = {}

            for update_item in updates_list:
                entity_token = update_item.get("entityToken")
                attr_name = update_item.get("attributeName")
                attr_value = update_item.get("attributeValue")

                if not entity_token or not attr_name:
                    # If invalid data, skip
                    continue

                # findEntityByToken returns a list of matching entities

                entity = self._get_obj_hash(entity_token)
                #Eif entity == None:

                print(f"{entity_token}: {entity.objectType} {entity.name} => {attr_value}")

                # Attempt to set the property
                final_val = None

                try:
                    setattr(entity, attr_name, attr_value)
                    # If we can read it back
                    final_val = getattr(entity, attr_name, None)



                except Exception:
                    # If attribute is read-only or invalid
                    final_val = None

                results[entity_token] = final_val

            return json.dumps(results)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()


    def _parse_function_call(self, func_call):
        """used by get_object_data """
        match = re.match(r'(\w+)\s*\((.*?)\)', func_call)
        if match:
            function_name = match.group(1)  # Extract function name
            raw_args = [arg.strip() for arg in match.group(2).split(',')] if match.group(2) else []

            # Convert numeric arguments to int or float
            def convert_arg(arg):
                if re.fullmatch(r'-?\d+', arg):  # Matches integers
                    return int(arg)
                elif re.fullmatch(r'-?\d*\.\d+', arg):  # Matches floats
                    return float(arg)
                return arg  # Return as string if not numeric

            parsed_args = [convert_arg(arg) for arg in raw_args]

            return function_name, parsed_args

    def get_object_data(self, object_path :list= ["comp1"], attributes_list:list=[""]) -> str:
        """
            {
                "name": "get_object_data",
                "description": "Gets Object attributes in the Fusion 360 design. The first element if object_path must be the name of a component, any following elements must be methods/atributes. The second_argument attributes_list is used to limit the response to only teh specifed attributs, this is just to save data. If attributes_list is set to [], the all attributes for the object will be returned. Some object attributes are methods the return more object, you pass theese to object path with the same syntax for calling a function. For example [comp1, sketches, item(0)], would return the first sketch represented as a JSON object. Another example: [comp3, bRepBodies.itemByName(Body1), volume] would return the volume of  body1 (bRepBody) in comp3 (component). This function allows you to query every possible element in the design by working your way through objects.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "object_path": {
                            "type": "array",
                            "items": { "type": "string" },
                            "description": "Object path array; the first element must by the name of a component. Any following elements will be interpreted as attributes of the component."
                        },

                        "attributes_list": {
                            "type": "array",
                            "items": { "type": "string" },
                            "description": "List of attributes whose values will be returned, when the first element is set to an empty string, all elements will be returned."
                        }

                    },

                    "required": ["get_object_data", "attributes_list"],

                    "returns": {
                        "type": "string",
                        "description": "A JSON-encoded string containing attributes/methods for the object"
                    }
                }
            }
        """

        try:
            app = adsk.core.Application.get()
            ui = app.userInterface
            design = adsk.fusion.Design.cast(app.activeProduct)

            component_name = object_path[0]
            targetObject, errors = self._find_component_by_name(component_name)

            if not targetObject:
                # if results, add error to return list
                return "Error"

            for attr_name in object_path[1:]:
                #print(f"attr_name: {attr_name}")

                if "(" in  attr_name:
                    attr_name, args = self._parse_function_call(attr_name)
                    targetObject = getattr(targetObject, attr_name)(*args)
                else:
                    targetObject = getattr(targetObject, attr_name)

            return_dict = {
                "objectPath": object_path,
                "objectVal": str(targetObject)
            }


            if len(attributes_list) ==1 and (attributes_list[0] == ""):
                attributes_list = dir(targetObject)
                attributes_list = [a for a in attributes_list if a[0] != "_"]

            for attr in attributes_list:

                try:

                    if hasattr(targetObject, attr) == False:
                        return_dict[attr]: f"object has not attribute: {attr}"
                        continue

                    attr_val = getattr(targetObject, attr, None)

                    attr_type = str(attr_val.__class__.__name__)
                    return_dict[attr] = {"type": attr_type, "val": str(attr_val) }

                    if attr == "itemByName":
                        item_names = [i.name for i in targetObject]
                        return_dict[attr]["itemNames"] = item_names

                except Exception as e:
                    #print(f"Error: {e}")
                    continue

            return json.dumps(return_dict)

        except:
            return f'Error: Failed to get/set component info:\n{traceback.format_exc()}'

    def get_model_parameters_by_component_as_json(self) -> str:
        """
        {
            "name": "get_model_parameters_by_component_as_json",
            "description": "Gathers model parameters from each component in the current Fusion 360 design, organizing them in a hierarchical structure that matches the assembly structure. Model parameters include any input parameter to features or construction geometry (e.g., hole diameters, extrusion distances, etc.). Returns a JSON-encoded string with design and parameter details such as name, expression, unit, value, and comment, grouped by component and sub-component.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "returns": {
                    "type": "string",
                    "description": "A JSON-encoded string representing the hierarchical structure of the current design’s components and their associated model parameters."
                }
            }
        }
        """

        app = adsk.core.Application.get()
        if not app:
            return json.dumps({})

        product = app.activeProduct
        if not product or not isinstance(product, adsk.fusion.Design):
            return json.dumps({})

        design = adsk.fusion.Design.cast(product)
        root_comp = design.rootComponent

        def gather_component_parameters(component):
            """
            Recursively gathers model parameters for the specified component and its children.
            Returns a dictionary with the component name, its model parameters, and its children.
            """
            comp_dict = {
                "name": component.name,
                "modelParameters": [],
                "children": []
            }

            # Collect all ModelParameters from this component
            for model_param in component.modelParameters:
                param_info = {
                    "name": model_param.name,
                    "created_by": model_param.createdBy.name,
                    "role": model_param.role,
                    "unit": model_param.unit or "",
                    "expression": model_param.expression or "",
                    "value": model_param.value,      # The resolved numeric value
                    "comment": model_param.comment or ""
                }
                comp_dict["modelParameters"].append(param_info)

            # Recursively gather data for child occurrences (sub-components)
            for occurrence in component.occurrences:
                # Each occurrence references a component
                sub_comp = occurrence.component
                if sub_comp:
                    # Gather parameters for the child component
                    child_comp_dict = gather_component_parameters(sub_comp)
                    comp_dict["children"].append(child_comp_dict)

            return comp_dict

        # Build a dictionary that represents the entire design structure
        design_data = {
            "designName": design.rootComponent.name,
            "rootComponent": gather_component_parameters(root_comp)
        }

        # Convert dictionary to a JSON string
        return json.dumps(design_data)


    def list_available_appearances(self) -> str:
        """
        {
            "name": "list_available_appearances",
            "description": "Generates a JSON list of all appearances available in the current Fusion 360 design, including local appearances and those in all appearance libraries.",
            "parameters": {
                "type": "object",
                "properties": {
                },
                "required": [],
                "returns": {
                    "type": "string",
                    "description": "A JSON array of appearances. Each element contains at least the name, id, and source library (or 'Design' if local)."
                }
            }
        }
        """
        try:
            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            design = adsk.fusion.Design.cast(product)

            appearance_list = []

            # ------------------------------------------------------------
            # 1) Get the local (design) appearances
            # ------------------------------------------------------------
            local_appearances = design.appearances
            for appearance in local_appearances:

                appearance_info = {
                    "name": appearance.name,
                    "id": appearance.id,
                    #"appearanceType": appearance.appearanceType,
                    "source": "Design"
                }
                appearance_list.append(appearance_info)

            # ------------------------------------------------------------
            # 2) Get the appearances from all appearance libraries
            # ------------------------------------------------------------
            material_libs = app.materialLibraries  # returns all material libraries, which can include appearance libraries
            for library in material_libs:
                # We only want libraries of type AppearanceLibraryType

                #if library.objectType == adsk.core.LibraryTypes.AppearanceLibraryType:

                if library.name not in ["Fusion Appearance Library"]:
                    continue

                for j in range(library.appearances.count):
                    lib_appearance = library.appearances.item(j)
                    appearance_info = {
                        "name": lib_appearance.name,
                        "id": lib_appearance.id,
                        #"appearanceType": lib_appearance.appearanceType,
                        "source": library.name  # e.g., "Fusion 360 Appearance Library"
                    }
                    appearance_list.append(appearance_info)

            # Convert the collected appearance data to a JSON string
            return json.dumps(appearance_list)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()

    def list_available_materials(self) -> str:
        """
            {
              "name": "list_available_materials",
              "description": "Lists all available material types in the Fusion 360 material libraries. Returns a JSON structure where each library includes its materials.",
              "parameters": {
                "type": "object",
                "properties": {
                },
                "required": [],
                "returns": {
                  "type": "string",
                  "description": "A JSON array. Each element represents a material library, containing its name and a list of materials (with name and id)."
                }
              }
            }
        """

        try:
            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            # The material libraries are accessed via app.materialLibraries
            mat_libraries = app.materialLibraries
            all_libraries_info = []

            for library in mat_libraries:

                # Check if it's a Material Library (rather than Appearance Library)
                if library.name in ["Fusion Material Library"]:

                    library_info = {
                        "libraryName": library.name,
                        "materials": []
                    }

                    # Enumerate materials in this library
                    for j in range(library.materials.count):
                        mat = library.materials.item(j)
                        library_info["materials"].append({
                            "name": mat.name,
                            "id": mat.id
                        })

                    all_libraries_info.append(library_info)

            # If you also want to list the materials in the design's local material collection,
            # you can add something like:
            #
            # product_design = adsk.fusion.Design.cast(product)
            # design_mats = product_design.materials
            # design_mats_info = {
            #   "libraryName": "local design materials",
            #   "materials": []
            # }
            # for k in range(design_mats.count):
            #   dm = design_mats.item(k)
            #   design_mats_info["materials"].append({"name": dm.name, "id": dm.id})
            # all_libraries_info.append(design_mats_info)

            return json.dumps(all_libraries_info)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()





    ###### old ######
    def _get_design_parameters_as_json(self) -> str:
        """
        {
            "name": "get_design_parameters_as_json",
            "description": "Collects all parameters from the active Fusion 360 design and returns a JSON-formatted string. Each parameter includes its name, unit, expression, numeric value, and comment. The resulting JSON structure contains an array of parameter objects, making it easy to review and utilize parameter data.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "returns": {
                    "type": "string",
                    "description": "A JSON-encoded string listing all parameters in the active design, including name, unit, expression, value, and comment for each parameter."
                }
            }
        }
        """

        app = adsk.core.Application.get()
        if not app:
            return json.dumps({"parameters": []})

        product = app.activeProduct
        # Ensure we have a Fusion Design
        if not product or not isinstance(product, adsk.fusion.Design):
            return json.dumps({"parameters": []})

        design = adsk.fusion.Design.cast(product)

        # Gather all parameters (this includes user parameters and model parameters)
        all_params = design.allParameters
        params_list = []

        for param in all_params:
            # Some parameters may not have a comment or expression.
            # We'll store empty strings if they're missing.
            name = param.name
            unit = param.unit or ""
            expression = param.expression or ""
            value = param.value  # Numeric value
            comment = param.comment or ""

            params_list.append({
                "name": name,
                "unit": unit,
                "expression": expression,
                "value": value,
                "comment": comment
            })

        # Build the final JSON object
        data = {"parameters": params_list}

        # Convert to a JSON string
        return json.dumps(data)

    def _get_entity_attributes(self,
                              entity_token_list: list = None,
                              attributes_list: list = ["name", "isLightBulbOn"]) -> str:
        """
        {
          "name": "get_entity_attributes",
          "description": "Retrieves the specified attributes from each entity referenced by the provided token list.",
          "parameters": {
            "type": "object",
            "properties": {
              "entity_token_list": {
                "type": "array",
                "description": "A list of entity tokens referencing Fusion 360 objects.",
                "items": { "type": "string" }
              },
              "attributes_list": {
                "type": "array",
                "description": "A list of attribute names to retrieve from each entity object.",
                "items": { "type": "string" }
              }
            },
            "required": ["entity_token_list", "attributes_list"],
            "returns": {
              "type": "string",
              "description": "A JSON string where each key is an entity token, and each value is a dict of { 'attributeName': value, ... }."
            }
          }
        }
        """

        try:
            if not entity_token_list or not isinstance(entity_token_list, list):
                return "Error: entity_token_list must be a non-empty list of strings."

            if not attributes_list or not isinstance(attributes_list, list):
                return "Error: attributes_list must be a non-empty list of attribute names."

            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            design = adsk.fusion.Design.cast(product)

            results_dict = {}

            for token in entity_token_list:

                # Attempt to locate the entity from its token
                try:
                    # findEntityByToken returns a sinlge element list
                    entities = design.findEntityByToken(token)
                    if len(entities) ==0:
                        continue

                    entity = entities[0]

                    if not entity:
                        # Could not find an object with that token
                        results_dict[token] = {
                            attr_name: None for attr_name in attributes_list
                        }
                        continue
                    attr_values = {}

                    for attr_name in attributes_list:
                        attr_val = getattr(entity, attr_name, None)
                        attr_values[attr_name] = attr_val
                    results_dict[token] = attr_values

                except Exception as e:
                    # If an error occurs processing this token, store None for all
                    results_dict[token] = {
                        attr_name: None for attr_name in attributes_list
                    }

            # Convert the results to JSON
            return json.dumps(results_dict)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()









class SetStateData(FusionSubmodule):

    def _parse_function_call(self, func_call):
        """used by get_object_data """
        match = re.match(r'(\w+)\s*\((.*?)\)', func_call)
        if match:
            function_name = match.group(1)  # Extract function name
            raw_args = [arg.strip() for arg in match.group(2).split(',')] if match.group(2) else []

            # Convert numeric arguments to int or float
            def convert_arg(arg):
                if re.fullmatch(r'-?\d+', arg):  # Matches integers
                    return int(arg)
                elif re.fullmatch(r'-?\d*\.\d+', arg):  # Matches floats
                    return float(arg)
                return arg  # Return as string if not numeric

            parsed_args = [convert_arg(arg) for arg in raw_args]

            return function_name, parsed_args



    def _set_object_attributes(self, object_path :list= ["comp1",  "sketches", "item(0)", "sketchCurves", "sketchCircles", "item(0)", "radius" ], new_val: dict= {"data_type": "float", "value": "10.0"} ) -> str:
        """
            {
                "name": "set_object_data",
                "description": "Sets Object attributes in the Fusion 360 design. You should use this function in conjunction with get_object_data. The first element must be the name of a component, any following elements must be methods/atributes. Ffor example if you wanted to change the radius of a sketch circle to 10cm you the object_path woudl be: [comp1, sketches, item(0), sketchCurves, sketchCircles, item(0), radius], and the new_val param would be {type: float, value_as_string: 10}. The new_val param has two keys, the value data type, and the value as a string. The value will be converted to the correct data type locally",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "object_path": {
                            "type": "array",
                            "items": { "type": "string" },
                            "description": "Object path array; the first element must by the name of a component. Any following elements will be interpreted as attributes of the component."
                        },
                        "new_val":{
                        "type": "object",
                        "properties": {
                            "data_type": {"type": "string"},
                            "value": {"type": "string"}
                        },
                        "description": "The type and value of the new attribute value"

                        }

                    },

                    "required": ["get_object_data", "new_val"],
                    "returns": {
                        "type": "string",
                        "description": "A JSON-encoded string containing attributes/methods for the object"
                    }
                }
            }
        """

        try:
            app = adsk.core.Application.get()
            ui = app.userInterface
            design = adsk.fusion.Design.cast(app.activeProduct)

            component_name = object_path[0]
            targetObject, errors = self._find_component_by_name(component_name)

            if not targetObject:
                # if results, add error to return list
                return "Error"

            targetAttr = object_path[-1]
            for attr_name in object_path[1: len(object_path)-1]:
                #print(f"attr_name: {attr_name}")

                if "(" in  attr_name:
                    attr_name, args = self._parse_function_call(attr_name)
                    targetObject = getattr(targetObject, attr_name)(*args)
                else:
                    targetObject = getattr(targetObject, attr_name)


            value = new_val["value"]
            data_type = new_val["data_type"]
            if data_type == "float":
                value = float(value)
            elif data_type == "int":
                value = int(value)
            elif data_type == "bool":
                if value.lower() == "true":
                    value = True
                elif value.lower() == "false":
                    value = False
            elif data_type == "list":
                value = json.loads(value)
            elif data_type == "dict":
                value = json.loads(value)

            current_val = getattr(targetObject,targetAttr)

            #targetObject = value
            setattr(targetObject, targetAttr, value)

            return f"Atrribute {object_path} set to {value}"


        except:
            return f'Error: Failed to get/set component info:\n{traceback.format_exc()}'


    def _set_object_data(self, object_path :list= ["comp1",  "sketches", "item(0)", "sketchCurves", "sketchCircles", "item(0)", "radius" ], new_val: dict= {"data_type": "float", "value": "10.0"} ) -> str:
        """
            {
                "name": "set_object_data",
                "description": "Sets Object attributes in the Fusion 360 design. You should use this function in conjunction with get_object_data. The first element must be the name of a component, any following elements must be methods/atributes. Ffor example if you wanted to change the radius of a sketch circle to 10cm you the object_path woudl be: [comp1, sketches, item(0), sketchCurves, sketchCircles, item(0), radius], and the new_val param would be {type: float, value_as_string: 10}. The new_val param has two keys, the value data type, and the value as a string. The value will be converted to the correct data type locally",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "object_path": {
                            "type": "array",
                            "items": { "type": "string" },
                            "description": "Object path array; the first element must by the name of a component. Any following elements will be interpreted as attributes of the component."
                        },
                        "new_val":{
                        "type": "object",
                        "properties": {
                            "data_type": {"type": "string"},
                            "value": {"type": "string"}
                        },
                        "description": "The type and value of the new attribute value"

                        }

                    },

                    "required": ["get_object_data", "new_val"],
                    "returns": {
                        "type": "string",
                        "description": "A JSON-encoded string containing attributes/methods for the object"
                    }
                }
            }
        """

        try:
            app = adsk.core.Application.get()
            ui = app.userInterface
            design = adsk.fusion.Design.cast(app.activeProduct)

            component_name = object_path[0]
            targetObject, errors = self._find_component_by_name(component_name)

            if not targetObject:
                # if results, add error to return list
                return "Error"

            targetAttr = object_path[-1]
            for attr_name in object_path[1: len(object_path)-1]:
                #print(f"attr_name: {attr_name}")

                if "(" in  attr_name:
                    attr_name, args = self._parse_function_call(attr_name)
                    targetObject = getattr(targetObject, attr_name)(*args)
                else:
                    targetObject = getattr(targetObject, attr_name)


            value = new_val["value"]
            data_type = new_val["data_type"]
            if data_type == "float":
                value = float(value)
            elif data_type == "int":
                value = int(value)
            elif data_type == "bool":
                if value.lower() == "true":
                    value = True
                elif value.lower() == "false":
                    value = False
            elif data_type == "list":
                value = json.loads(value)
            elif data_type == "dict":
                value = json.loads(value)

            current_val = getattr(targetObject,targetAttr)

            #targetObject = value
            setattr(targetObject, targetAttr, value)

            return f"Atrribute {object_path} set to {value}"


        except:
            return f'Error: Failed to get/set component info:\n{traceback.format_exc()}'



    def _set_component_child_attribute_values(self, object_array:list=[

            {"component_name": "comp1",
             "object_type":"sketches",
             "object_name":"Sketch1",
             "action": "isLightBulbOn", "value": "true"
             },

            {"component_name": "comp1",
             "object_type":"this",
             "object_name":"this",
             "action": "isBodiesFolderLightBulbOn", "value": False
             },

            {"component_name": "GPTEST2 v1",
             "object_type":"occurrences",
             "object_name":"comp1:1",
             "action": "isLightBulbOn", "value": "true"
             },

    ] ) -> str:
        """
        {
            "name": "set_component_child_attribute_values",
            "description": "Sets attribute values for component child objects, suck as occurrences, sketches, bRepBodies,joints, jointOrigins, etc.. When setting visibility (isLightBulbOn) the value should be a bool",
            "parameters": {
                "type": "object",
                "properties": {
                    "object_array": {
                        "type": "array",
                        "description": "Array of objects to set value or perfom action",
                        "items": {
                            "type": "object",
                            "properties": {
                                "component_name": {
                                    "type": "string",
                                    "description": "name of the parent component containing the object"
                                },
                                "object_type": {
                                    "type": "string",
                                    "description": "type of object to delete",
                                    "enum": [
                                        "sketches",
                                        "bRepBodies",
                                        "meshBodies",
                                        "joints",
                                        "jointOrigins",
                                        "occurrences",
                                        "rigidGroups" ]
                                },
                                "object_name": {
                                    "type": "string",
                                    "description": "The name of the object to delete"
                                },

                                "action": {
                                    "type": "string",
                                    "description": "action to perform",

                                    "enum": [
                                        "isLightBulbOn",
                                        "opacity",
                                        "material",
                                        "appearance",
                                        "isGrounded",
                                        "isGroundToParent"
                                        ]
                                },
                                "value": {
                                    "type": "string",
                                    "description": "action to perform"
                                }

                            },

                            "required": ["component_name", "object_type", "object_name", "action", "value"]
                        }

                    }
                },
                "required": ["object_array"],
                "returns": {
                    "type": "string",
                    "description": "A message indicating success or failure of the options"
                }
            }
        }
        """

        try:
            # Access the active design.
            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)
            rootComp = design.rootComponent

            # check arg type
            if not isinstance(object_array, list):
                return "Error: object_array must be an array/ list"

            object_enums = [
                "sketches",
                "bRepBodies",
                "meshBodies",
                "joints",
                "jointOrigins",
                "occurrences",
                "rigidGroups",
                "this",
            ]

            # add object to delete to dict, faster this way
            action_dict = {}

            results = []
            # jonied as string and returned
            # items in array, each representing a delete task
            for object_dict in object_array:
                component_name = object_dict.get("component_name")
                object_type = object_dict.get("object_type")
                object_name = object_dict.get("object_name")
                action = object_dict.get("action")
                value = object_dict.get("value")

                # all objects have a parent/target component
                targetComponent, errors = self._find_component_by_name(component_name)
                #print(dir(targetComponent))

                if not targetComponent:
                    # if results, add error to return list
                    results.append(errors)
                    continue

                # comp.sketches, comp.bodies, comp.joints etc
                object_class = getattr(targetComponent, object_type, None)

                # check if delete object class list exists
                if object_class == None:
                    results.append(f"Error: Component {component_name} has not attribute '{object_type}'.")
                    continue



                if object_type != "this":
                    # check that attr has 'itemByName' method before calling it
                    if hasattr(object_class, "itemByName") == False:
                        errors = f"Error: Component {component_name}.{object_type} has no method 'itemByName'."
                        results.append(errors)
                        continue
                    # select object by name, sketch, body, joint, etc
                    target_object = object_class.itemByName(object_name)
                else:
                    target_object = object_class


                # check if item by name is None
                if target_object == None:
                    errors = f"Error: Component {component_name}: {object_type} has no item {object_name}."
                    available_objects = [o.name for o in object_class]
                    errors += f" Available objects in {component_name}.{object_type}: {available_objects}"
                    results.append(errors)
                    continue


                # check if item has the associated action attribute
                if hasattr(target_object, action) == False:
                    errors = f"Error: Component {component_name}.{object_type} object {object_name} has no attribute {action}."
                    results.append(errors)
                    continue

                object_action_dict = {
                    "target_object": target_object,
                    "action": action,
                    "value": value
                }

                action_dict[f"{component_name}:{object_type}:{target_object.name}:{action}"] = object_action_dict 



            #if len(list(delete_dict.keys())) == 0:
            if len(action_dict) == 0:
                results.append(f"No objects found")

            for k, v in action_dict.items():

                target_object = v["target_object"]
                action = v["action"]
                value = v["value"]

                if value.lower() == "true":
                    value = True
                elif value.lower() == "false":
                    value = False

                print(action)
                set_result = setattr(target_object, action, value)
                results.append(f"Set {target_object} {action} to {value}: {set_result}")


            results.append(f"Success")

            return "\n".join(results).strip()

        except:
            return f'Error: Failed to modify objects:\n{traceback.format_exc()}'



    def _set_component_attributes(self, object_array:list=[

            { "component_name": "comp1",
             "action":"isBodiesFolderLightBulbOn",
             "value": True
             },

            {"component_name": "comp1",
             "action":"isSketchFolderLightBulbOn",
             "value": True

             },

    ] ) -> str:

        """
        {
            "name": "set_component_attributes",
            "description": "Sets properties/attributes for a specificeomponent object",
            "parameters": {
                "type": "object",
                "properties": {
                    "object_array": {
                        "type": "array",
                        "description": "Array of objects to set value or perfom action",
                        "items": {
                            "type": "object",
                            "properties": {
                                "component_name": {
                                    "type": "string",
                                    "description": "name of the target component"
                                },
                                "action": {
                                    "type": "string",
                                    "description": "action to perform",
                                    "enum": [
                                        "isBodiesFolderLightBulbOn",
                                        "isConstructionFolderLightBulbOn",
                                        "isCanvasFolderLightBulbOn",
                                        "isDecalFolderLightBulbOn",
                                        "isJointsFolderLightBulbOn",
                                        "isOriginFolderLightBulbOn",
                                        "isSketchFolderLightBulbOn",
                                        "isLightBulbOn"
                                    ]
                                },
                                "value": {
                                    "type": "string",
                                    "description": "action to perform"
                                }
                            },
                            "required": ["component_name", "action", "value"]
                        }
                    }
                },
                "required": ["object_array"],
                "returns": {
                    "type": "string",
                    "description": "A message indicating success or failure of the options"
                }
            }
        }
        """

        try:
            # Access the active design.
            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)
            rootComp = design.rootComponent

            # check arg type
            if not isinstance(object_array, list):
                return "Error: object_array must be an array/ list"

            object_enums = [
                "isBodiesFolderLightBulbOn",
                "isConstructionFolderLightBulbOn",
                "isCanvasFolderLightBulbOn",
                "isDecalFolderLightBulbOn",
                "isJointsFolderLightBulbOn",
                "isOriginFolderLightBulbOn",
                "isSketchFolderLightBulbOn"
            ]

            # add object to delete to dict, faster this way
            action_dict = {}

            results = []
            # jonied as string and returned
            # items in array, each representing a delete task
            for object_dict in object_array:
                component_name = object_dict.get("component_name")
                action = object_dict.get("action")
                value = object_dict.get("value")

                # all objects have a parent/target component
                targetComponent, errors = self._find_component_by_name(component_name)

                if not targetComponent:
                    # if results, add error to return list
                    results.append(errors)
                    continue

                # check if item has the associated action attribute
                if hasattr(targetComponent, action) == False:
                    errors = f"Error: Component {component_name} has no attribute {action}."
                    results.append(errors)
                    continue

                object_action_dict = {
                    "target_object": targetComponent,
                    "action": action,
                    "value": value
                }

                action_dict[f"{component_name}:{action}"] = object_action_dict 

                #results.append(f'Added {component_name}.{object_type} "{target_object.name}" to delete list.')


            #if len(list(delete_dict.keys())) == 0:
            if len(action_dict) == 0:
                results.append(f"No objects to delete.")

            for k, v in action_dict.items():
                target_object = v["target_object"]
                action = v["action"]
                value = v["value"]

                if isinstance(value, str):
                    if value.lower() == "true":
                        value = True
                    elif value.lower() == "false":
                        value = False

                print(action)
                set_result = setattr(target_object, action, value)
                results.append(f"Set {target_object} {action} to {value}: {set_result}")


            results.append(f"Success")

            return "\n".join(results).strip()

        except:
            return f'Error: Failed to modify components:\n{traceback.format_exc()}'









    def set_appearance_on_components(
            self, appearance_updates: list = [{"component_name": "comp1","appearance_name":"Paint - Enamel Glossy (Green)"}]) -> str:

            """
                {
                  "name": "set_appearance_on_components",
                  "description": "Sets the appearance on a list of components. Each item in appearance_updates is {'component_name': <COMPONENT_NAME>, 'appearance_name': <APPEARANCE_NAME>}.",
                  "parameters": {
                    "type": "object",
                    "properties": {
                      "appearance_updates": {
                        "type": "array",
                        "description": "An array of objects with the form {'component_name': <COMPONENT_NAME>, 'appearance_name': <APPEARANCE_NAME>}.",
                        "items": {
                          "type": "object",
                          "properties": {
                            "component_name": {
                              "type": "string"
                            },
                            "appearance_name": {
                              "type": "string"
                            }
                          },
                          "required": ["component_name", "appearance_name"]
                        }
                      }
                    },
                    "required": ["appearance_updates"],
                    "returns": {
                      "type": "string",
                      "description": "A summary message about which components were updated or any errors encountered."
                    }
                  }
                }
            """
            try:
                if not appearance_updates or not isinstance(appearance_updates, list):
                    return "Error: Must provide an array of updates in the form [{'component_name': '...', 'appearance_name': '...'}, ...]."

                app = adsk.core.Application.get()
                if not app:
                    return "Error: Fusion 360 is not running."

                product = app.activeProduct
                if not product or not isinstance(product, adsk.fusion.Design):
                    return "Error: No active Fusion 360 design found."

                design = adsk.fusion.Design.cast(product)
                root_comp = design.rootComponent

                # A helper function to find an appearance by name in the design
                # (Optionally search the appearance libraries if not found in design).
                def find_appearance_by_name(appearance_name: str):
                    #print(appearance_name)

                    # 1) Check the design's local appearances
                    local_appearance = design.appearances.itemByName(appearance_name)
                    if local_appearance:
                        return local_appearance

                    # 2) Optionally, check libraries if not found in local. Comment this out if not needed.
                    appearance_libraries = app.materialLibraries
                    for a_lib  in appearance_libraries:
                        if a_lib.name not in ["Fusion Appearance Library"]:
                            continue

                        lib_app = a_lib.appearances.itemByName(appearance_name)

                        if lib_app:
                            # You typically need to copy the library appearance into the design before applying
                            return design.appearances.addByCopy(lib_app, appearance_name)

                    return None

                results = []

                # Process each update item
                for update in appearance_updates:
                    # Validate each item in the array
                    if not isinstance(update, dict):
                        results.append("Error: Appearance update must be a dictionary.")
                        continue

                    comp_name = update.get("component_name")
                    app_name = update.get("appearance_name")
                    if not comp_name or not app_name:
                        results.append(f"Error: Missing component_name or appearance_name in {update}.")
                        continue

                    # Find the appearance by name
                    appearance = find_appearance_by_name(app_name)
                    if not appearance:
                        results.append(f"Error: Appearance '{app_name}' not found in design or libraries.")
                        continue

                    # Find all occurrences that reference this component name
                    #self._find_component_by_name(component_name)

                    found_occurrences = []
                    for occ in root_comp.allOccurrences:
                        if occ.component.name == comp_name:
                            found_occurrences.append(occ)

                    #  in case occurrences was passed in
                    if not found_occurrences:
                        found_occurrences.append(self._find_occurrence_by_name(comp_name))


                    if not found_occurrences:
                        results.append(f"Error: No occurrences found for component '{comp_name}'.")
                        continue

                    # Apply the appearance override to each matching occurrence
                    for occ in found_occurrences:
                        try:
                            # Setting the appearance property on an occurrence
                            occ.appearance = appearance
                            # If needed, you can enforce override with:
                            # occ.appearance.isOverride = True
                        except Exception as e:
                            results.append(f"Error: error setting appearance on occurrence {occ.name}: {str(e)}")
                            continue

                    results.append(f"Set appearance '{app_name}' on component '{comp_name}' ({len(found_occurrences)} occurrence(s)).")

                print("\n".join(results))
                return "\n".join(results)

            except:
                return "Error: An unexpected exception occurred:\n" + traceback.format_exc()


    def rename_component(self, component_name: str, new_name: str) -> str:
        """
            {
              "name": "rename_component",
              "parameters": {
                "type": "object",
                "properties": {
                  "component_name": {
                    "type": "string",
                    "description": "The name of the Fusion 360 component to be renamed."
                  },
                  "new_name": {
                    "type": "string",
                    "description": "The new name to assign to the component."
                  }
                },
                "required": [
                  "component",
                  "new_name"
                ]
              },
              "description": "Renames a specified component in Fusion 360 to a new name."
            }
        """
        try:
            targetComponent, errors = self._find_component_by_name(component_name)
            if not targetComponent:
                return errors

            # Set the new name for the component
            targetComponent.name = new_name
            return new_name

        except Exception as e:
            return 'Error: Failed to rename the component:\n{}'.format(new_name)




