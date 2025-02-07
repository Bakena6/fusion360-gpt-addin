# document data

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
import base64
import re
import hashlib

from ... import config
from ...lib import fusion360utils as futil

# send info to html palette
from .shared import ToolCollection 

def print(string):
    """redefine print for fusion env"""
    futil.log(str(string))
print(f"RELOADED: {__name__.split("%2F")[-1]}")



class GetStateData(ToolCollection):
    """
    methods used by Realtime API to retrive state of Fusion document
    """

    #def __init__(self):
    #    super().__init__()  # Call the base class constructor

    #def retrieve_objects_by_token(token_list: list=[]) -> list:

    def _get_ent_attrs(self, entity, attr_list):
        """
        get entity info, return as dict 
        """
        ent_info = { }
        for attr in attr_list:
            try:

                if "." in attr:

                    attr0, attr1 = attr.split(".")

                    try:
                        sub_ent = getattr(entity, attr0, None)
                    except Exception as e:
                        print(e)
                        continue

                    if sub_ent is None:
                        continue

                    try:
                        attr_val = getattr(sub_ent, attr1)
                    except Exception as e:
                        print(e)
                        continue

                    if attr1 == "entityToken":
                        attr_val = self.set_obj_hash(attr_val, sub_ent)

                    ent_info[attr] = attr_val


                elif hasattr(entity, attr) == True:
                    attr_val = getattr(entity, attr)
                    if attr == "entityToken":
                        attr_val = self.set_obj_hash(attr_val, entity)

                    ent_info[attr] = attr_val

            except Exception as e:
                print(e)

        return ent_info


    @ToolCollection.tool_call
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
            print("func_run")

            # Access the active design
            if design:
                # Return the name of the root component
                return design.rootComponent.name
            else:
                return None

        except Exception as e:
            return None

    # called get_by design_as_json
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
                    "isOriginFolderLightBulbOn",
                    "isSketchFolderLightBulbOn",
                    "description",
                    "opacity",
                    "entityToken",
                    "transform"
                ]

                # iterable attr attributes
                iter_attrs_attrs = [
                    "name",
                    "entityToken"
                ]

                for attr in attr_list:
                    attr_val =  getattr(comp, attr, None)
                    if attr == "entityToken":
                        attr_val = self.set_obj_hash(comp.name, comp)

                    comp_data[attr] = attr_val

                # attributes that return iterables
                iter_attr_list = [
                    "occurrences",
                    "bRepBodies",
                    "sketches",
                    "jointOrigins",
                    "joints",
                    #"modelParameters",
                ]

                # iterable attributes: bRepBodes, Sketches
                for iter_attr in iter_attr_list:
                    attr_val = getattr(comp, iter_attr, None)

                    if attr_val == None:
                        continue

                    if len(attr_val) == 0:
                        continue

                    # iterate over sketch, bRepBody
                    sub_ent_attrs = []
                    for sub_obj in attr_val:
                        ent_info = self._get_ent_attrs(sub_obj, iter_attrs_attrs)
                        sub_ent_attrs.append(ent_info)

                    comp_data[iter_attr] =sub_ent_attrs 

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



    @ToolCollection.tool_call
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
                "joints",
                #"rigidGroups"

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
                "opacity",
                "visibleOpacity",
                "isSuppressed",
                "isIsolated",
                #"isFlipped",
                "isLocked"
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
                    #print(f"{object_name}")

                    # joints that reside in the root component fail even though attr exists
                    try:
                        # body, joint, sketch etc
                        objectArray = getattr(occ, object_name)
                    except Exception as e:
                        print(f"  Error 1: <{object_name}> {e}")
                        try:
                            root_comp = design.rootComponent
                            objectArray = getattr(root_comp, object_name)
                            print(f"  {object_name} found in root comp!")
                        except Exception as e:
                            print(f" Error 2: {object_name} {e}\n{traceback.format_exc()}")
                            continue

                        #print(f"try")
                        #print(f"hasattr: {occ.name}:{object_name}: {hasattr(occ, object_name)}")




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


        #print(json.dumps(design_data, indent=4))
        # Convert dictionary to a JSON string with indentation
        return json.dumps(design_data)

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

    @ToolCollection.tool_call
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

    @ToolCollection.tool_call
    def get_timeline_entities(self) -> str:
        """
            {
              "name": "get_timeline_entities",
              "description": "Returns a JSON array describing all items in the Fusion 360 timeline, including entity info, errors/warnings, healthState, etc.",

              "parameters": {
                "type": "object",
                "properties": { },
                "required": [],
                "returns": {
                  "type": "string",
                  "description": "A JSON array; each entry includes timeline item data such as index, name, entityType, healthState, errorOrWarningMessage, and the its associated entity, whch can be any type of Fusion 360 object. The entityToken is provide for the associated entity."
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
            timeline = design.timeline

            timeline_attr_names = [
                "name",
                "index",
                "isSuppressed",
                "errorOrWarningMessage",
                "healthState",
                "parentGroup",
                "isGroup",
                "objectType",
                "entity.name",
                "entity.entityToken",

            ]


            timeline_info = []
            for t_item in timeline:

                if not t_item:
                    continue


                item_data = self._get_ent_attrs(t_item, timeline_attr_names)

                # Parent group reference
                if t_item.parentGroup:
                    item_data["parentGroupIndex"] = t_item.parentGroup.index
                    item_data["parentGroupName"] = t_item.parentGroup.name

                # Entity info
                entity = t_item.entity
                if entity:
                    # We'll store a few general properties if available
                    entity_type = entity.objectType  # e.g. 'adsk::fusion::ExtrudeFeature'
                    item_data["entityType"] = entity_type

                    # Many entities have a "name" property, but not all. We'll try/catch.
                    entity_name = getattr(entity, "name", None)
                    if entity_name:
                        item_data["entityName"] = entity_name

                    # Optionally gather more info if you like:
                    # e.g. if entity_type indicates a feature, you could store
                    # entity.isSuppressed or others. Just be sure to check for availability.
                else:
                    item_data["entityType"] = None  # E.g., might be a group or unknown.

                timeline_info.append(item_data)

            return json.dumps(timeline_info)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()
    @ToolCollection.tool_call
    def get_model_parameters_by_component(self) -> str:
        """
        {
            "name": "get_model_parameters_by_component",
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
                "componentName": component.name,
                "modelParameters": [],
                "children": []
            }

            # Collect all ModelParameters from this component
            for model_param in component.modelParameters:
                param_info = {
                    "name": model_param.name,
                    "associatedComponentName": component.name,
                    "createdBy": model_param.createdBy.name,
                    "role": model_param.role,
                    "unit": model_param.unit or "",
                    "expression": model_param.expression or "",
                    "value": model_param.value,      # The resolved numeric value
                    "enityToken": self.set_obj_hash(model_param.entityToken, model_param),
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


    @ToolCollection.tool_call
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

    @ToolCollection.tool_call
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





class SetStateData(ToolCollection):

    @ToolCollection.tool_call
    def set_entity_values(self,
                         entity_token_list: list = [],
                         attribute_name: str = "isLightBulbOn",
                         attribute_value=True) -> str:
        """
        {
          "name": "set_entity_values",
          "description": "Sets a single property on each referenced entity by token. The function sets entity.<attribute_name> = attribute_value for all tokens in entity_token_list, if it is writable.",
          "parameters": {
            "type": "object",

            "properties": {
              "entity_token_list": {
                "type": "array",
                "description": "A list of strings, each referencing an entity token to update.",
                "items": {
                  "type": "string"
                }
              },
              "attribute_name": {
                "type": "string",
                "description": "The name of the attribute/property to set on each entity.",
                "enum": [
                    "name",
                    "value",
                    "isLightBulbOn",
                    "opacity",
                    "isGrounded",
                    "isIsolated",
                    "isLocked",
                    "isBodiesFolderLightBulbOn",
                    "isCanvasFolderLightBulbOn",
                    "isConstructionFolderLightBulbOn",
                    "isDecalFolderLightBulbOn",
                    "isJointsFolderLightBulbOn",
                    "isOriginFolderLightBulbOn",
                    "isSketchFolderLightBulbOn",
                    "description"
                ]
              },
              "attribute_value": {
                "type": ["boolean","number","string","null"],
                "description": "The new value to assign to the specified attribute on each entity."
              }
            },
            "required": ["entity_token_list", "attribute_name", "attribute_value"],
            "returns": {
              "type": "string",
              "description": "A JSON object mapping each entity token to the final property value, or null if an error occurred."
            }
          }
        }
        """


        try:
            if not entity_token_list or not isinstance(entity_token_list, list):
                return "Error: entity_token_list must be a non-empty list of strings."
            if not attribute_name:
                return "Error: attribute_name is required."

            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            design = adsk.fusion.Design.cast(product)

            # Final results mapped: token -> final value or None
            results = {}

            for token in entity_token_list:
                if not token:
                    continue

                final_val = None

                entity = self.get_hash_obj(token)
                if not entity:
                    results[token] = f"Error: no object found for entity_token: {token}"
                    continue

                object_type = entity.objectType.split(":")[-1]
                object_name = entity.name

                attr_exists = hasattr(entity, attribute_name)
                if attr_exists == False:
                    results[token] = f"Error: {object_type} '{object_name}' ({token}) has no attribute '{attribute_name}'"
                    continue

                try:
                    setattr(entity, attribute_name, attribute_value)
                    # Read back the property
                    new_val = getattr(entity, attribute_name, None)

                    if attribute_value != new_val:
                        final_val = f"Error: value not set on attribute '{attribute_name}' on {object_type} '{object_name}' ({token})."
                    else:
                        final_val = f"Success: attribute '{attribute_name}' set to '{new_val}' on {object_type} '{object_name}' ({token})."

                except Exception as e:
                    # If attribute is read-only or invalid
                    final_val = f"Error: failed to set attribute '{attribute_name}' on {object_type} '{object_name}' ({token}): {e}."

                results[token] = final_val

            return json.dumps(results)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()


    @ToolCollection.tool_call
    def set_appearance_on_entities(
        self,
        entity_token_list: list = [],
        appearance_name: str = "Paint - Enamel Glossy (Green)"
    ) -> str:
        """
        {
          "name": "set_appearance_on_entities",
          "description": "Sets the given appearance on each entity referenced by token. Typically, these entities are occurrences. The function searches design and libraries to find/copy the appearance.",
          "parameters": {
            "type": "object",
            "properties": {
              "entity_token_list": {
                "type": "array",
                "description": "A list of entity tokens referencing the occurrences or other valid objects in Fusion 360.",
                "items": { "type": "string" }
              },
              "appearance_name": {
                "type": "string",
                "description": "The name of the appearance to apply."
              }
            },
            "required": ["entity_token_list", "appearance_name"],
            "returns": {
              "type": "string",
              "description": "A summary of the updates or any errors encountered."
            }
          }
        }
        """

        try:
            if not entity_token_list or not isinstance(entity_token_list, list):
                return "Error: entity_token_list must be a non-empty list of strings."
            if not appearance_name:
                return "Error: appearance_name is required."

            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            design = adsk.fusion.Design.cast(product)

            # Helper function to locate or copy an appearance by its name

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



            # Attempt to find the appearance
            appearance = find_appearance_by_name(appearance_name)
            if not appearance:
                return f"Error: Appearance '{appearance_name}' not found in design or libraries."

            # We'll store messages for each token processed
            results = []

            # A simple helper to find the first entity matching a token
            def get_entity_by_token(entity_token: str):
                entity = self.get_hash_obj(entity_token)
                return entity

            # Process each entity token
            for token in entity_token_list:
                if not token:
                    results.append("Error: Empty token encountered.")
                    continue

                entity = get_entity_by_token(token)
                if not entity:
                    results.append(f"Error: No entity found for token '{token}'.")
                    continue

                # Typically, only Occurrences have an .appearance property.
                # Some other entities (e.g., bodies) do as well, but many do not.
                if hasattr(entity, "appearance"):
                    try:
                        entity.appearance = appearance
                        results.append(f"Set appearance '{appearance_name}' on entity (token={token}).")
                    except Exception as e:
                        results.append(f"Error setting appearance on token={token}: {str(e)}")
                else:
                    results.append(f"Error: Entity (token={token}) does not support .appearance.")

            return "\n".join(results)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()


    @ToolCollection.tool_call
    def delete_entities(self, entity_token_list: list = []) -> str:
        """
        {
          "name": "delete_entities",
          "description": "Deletes all entities in in the entity_token_list by calling the deleteMe() method. This should be used when ever an object/entity needs to be deleted.",
          "parameters": {
            "type": "object",

            "properties": {
              "entity_token_list": {
                "type": "array",
                "description": "A list of strings, each referencing an entity token to update.",
                "items": {
                  "type": "string"
                }
              }
            },
            "required": ["entity_token_list"],
            "returns": {
              "type": "string",
              "description": "A JSON object mapping each entity token to the deletion status message."
            }
          }
        }
        """


        try:
            if not entity_token_list or not isinstance(entity_token_list, list):
                return "Error: entity_token_list must be a non-empty list of strings."
            #if not attribute_name:
            #    return "Error: attribute_name is required."

            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            design = adsk.fusion.Design.cast(product)

            # Final results mapped: token -> final value or None
            results = {}

            for token in entity_token_list:
                if not token:
                    continue

                final_val = None

                entity = self.get_hash_obj(token)
                if not entity:
                    results[token] = f"Error: no object found for entity_token: {token}"
                    continue

                object_type = entity.objectType.split(":")[-1]
                object_name = entity.name

                attribute_name = "deleteMe"
                attr_exists = hasattr(entity, attribute_name)
                if attr_exists == False:
                    results[token] = f"Error: {object_type} '{object_name}' ({token}) has no attribute '{attribute_name}'"
                    continue

                try:
                    attr_obj = getattr(entity, attribute_name)
                    # call deleteMe
                    deletion_val = attr_obj()

                    if deletion_val == True:
                        final_val = f"Success: Deleted {object_type} '{object_name}' ({token})."
                    else:
                        final_val = f"Error: Could not delete {object_type} '{object_name}' ({token})."

                except Exception as e:
                    # If attribute is read-only or invalid
                    final_val = f"Error: failed to delete {object_type} '{object_name}' ({token}): {e}."

                results[token] = final_val

            return json.dumps(results)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()




