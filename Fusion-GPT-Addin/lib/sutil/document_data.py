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


from ... import config
from ...lib import fusion360utils as futil

# send info to html palette
from .shared import FusionSubmodule

def print(string):
    """redefine print for fusion env"""
    futil.log(str(string))



class StateData(FusionSubmodule):
    """
    methods used by Realtime API to retrive state of Fusion document
    """
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

    def _get_ent_attrs(self, entity, attr_list):
        """
        get entity info
        """

        ent_info = { }
        for attr in attr_list:
            if hasattr(entity, attr) == True:

                attr_val = getattr(entity, attr)

                if isinstance(attr_val, adsk.core.Point3D):
                    attr_val = attr_val.asArray()
                elif isinstance(attr_val, adsk.core.Matrix3D):
                    attr_val = attr_val.asArray()

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

            comp_dict = {
                "component_name": component.name,
                "component_entityToken": component.entityToken,
                "occurrence_data": None,
            }

            object_types = [
                "occurrences",
                "bRepBodies",
                "sketches",
                "joints",
                "jointOrigins"
            ]



            #occ_params = ["name", "isLightBulbOn", "transform", "translation", "entityToken"]
            #if occ != None:
            #    occurrence_data = self._get_ent_attrs(occ, occ_params)
            #    comp_dict["occurrence_data"] = occurrence_data


            global_params = [ "entityToken", "name", "isLightBulbOn"]
            for objectType in object_types:
                object_array = getattr(component, objectType)
                for object_inst in object_array:
                    ent_info = self._get_ent_attrs(object_inst, global_params)
                    if comp_dict.get(objectType) == None:
                        comp_dict[objectType] = []

                    comp_dict[objectType].append(ent_info)


            # Recursively gather data for all child occurrences
            for index, occ in enumerate(component.occurrences):
                sub_comp = occ.component
                if sub_comp:
                    occ_data = get_component_data(occ, sub_comp)

                    if comp_dict.get(objectType) == None:
                        comp_dict["occurrences"] = []

                    comp_dict["occurrences"].append(occ_data)

            return comp_dict


        # Build a dictionary that holds the entire design structure
        design_data = {
            "designName": design.rootComponent.name,
            "rootComponent": get_component_data(None, design.rootComponent)
        }

        # Convert dictionary to a JSON string with indentation
        return json.dumps(design_data, indent=4)


    def get_entity_attributes(self,
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
                    print(e)
                    # If an error occurs processing this token, store None for all
                    results_dict[token] = {
                        attr_name: None for attr_name in attributes_list
                    }

            # Convert the results to JSON
            return json.dumps(results_dict)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()



    def _parse_function_call(self, func_call):
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
                "description": "Gets and sets Object attributes in the Fusion 360 design. The first element must be the name of a component, any following elements must be methods/atributes. For example [comp1, Sketches, item(0), would return the first sketch represented as a JSON object. To set an attribute value, you will call one of the _set methods, for example if you wanted to change the radius of a sketch circle to 10cm you would use [comp1, sketches, item(0), sketchCurves, sketchCircles,item(0), _set_radius(10)]. As another you can get geometry data on the centerpoint of the first circle in the first sketch of component 1 with the following string",
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
                            "description": "List of attributes whose values will be returned"
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
                    print(f"Error: {e}")
                    continue

            print(json.dumps(return_dict, indent=4))
            return json.dumps(return_dict)

        except:
            return f'Error: Failed to get/set component info:\n{traceback.format_exc()}'

    def set_object_data(self, object_path :list= ["comp1",  "sketches", "item(0)", "sketchCurves", "sketchCircles", "item(0)", "radius" ], new_val: dict= {"data_type": "float", "value": "10.0"} ) -> str:
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

            print(f"value: {value}")
            current_val = getattr(targetObject,targetAttr)
            print(f"current_val: {current_val}")
            #targetObject = value
            setattr(targetObject,targetAttr, value)


        except:
            return f'Error: Failed to get/set component info:\n{traceback.format_exc()}'



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
        return json.dumps(data, indent=4)

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
        return json.dumps(design_data, indent=4)


    def get_sketch_profiles(self, component_name: str = "comp1", sketch_name: str = "Sketch1"):
        """
        {
            "name": "get_sketch_profiles",
            "description": "Retrieves all the profiles from a specified sketch within a specified component. Returns a JSON-like object containing each profile's area, center point, and areaIndex (with 0 being the largest profile).",
            "parameters": {
                "type": "object",
                "properties": {
                    "component_name": {
                        "type": "string",
                        "description": "The name of the component in the current design containing the sketch."
                    },
                    "sketch_name": {
                        "type": "string",
                        "description": "The name of the sketch inside the specified component."
                    }
                },
                "required": ["component_name", "sketch_name"],
                "returns": {
                    "type": "object",
                    "description": "A JSON-like dictionary with a 'profiles' key, listing each profile's area, centroid (x, y, z), and areaIndex sorted by descending area. If an error occurs, a string describing the error is returned instead."
                }
            }
        }
        """
        try:
            # Access the active design
            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)

            # Use a local helper method to find the target component
            targetComponent, errors = self._find_component_by_name(component_name)
            if not targetComponent:
                return errors

            targetSketch, errors = self._find_sketch_by_name(targetComponent, sketch_name)
            if not targetSketch:
                return errors

            if not targetSketch.profiles or targetSketch.profiles.count == 0:
                return "No profiles found in the sketch."

            # Gather profile information (area and centroid)
            profile_data = []
            for profile in targetSketch.profiles:
                props = profile.areaProperties()
                area = props.area
                centroid = props.centroid
                profile_data.append({
                    "profile": profile,  # Storing the actual profile object (if needed)
                    "area": area,
                    "centroid": [centroid.x, centroid.y, centroid.z]
                })

            # Sort profiles by descending area
            profile_data.sort(key=lambda p: p["area"], reverse=True)

            # Create the final list of profile info for JSON-like output
            results = []
            for idx, data in enumerate(profile_data):
                results.append({
                    "areaIndex": idx,  # 0 = largest
                    "area": data["area"],
                    "centerPoint": data["centroid"]
                })

            # Return the JSON-like structure
            return json.dumps({ "profiles": results })

        except Exception as e:
            return f"Error: {e}"

    def list_edges_in_body(self, component_name: str="comp1", body_name: str="Body1") -> str:
        """
        {
            "name": "list_edges_in_body",
            "description": "Generates a list of all edges in a specified BRep body, including position and orientation data that can be used for future operations like fillets or chamfers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "component_name": {
                        "type": "string",
                        "description": "The name of the component in the current design containing the body."
                    },
                    "body_name": {
                        "type": "string",
                        "description": "The name of the target body whose edges will be listed."
                    }
                },
                "required": ["component_name", "body_name"],
                "returns": {
                    "type": "string",
                    "description": "A JSON array of edge information. Each element contains 'index', 'geometryType', 'length', bounding-box data, and geometry-specific data like direction vectors or center points."
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

            # Locate the target component by name (assuming you have a helper method)
            targetComponent, errors = self._find_component_by_name(component_name)
            if not targetComponent:
                return errors

            body, errors = self._find_body_by_name(targetComponent, body_name)
            if not body:
                return errors

            edges = body.edges
            edge_data_list = []

            for i, edge in enumerate(edges):
                geom = edge.geometry
                geometryType = type(geom).__name__  # e.g., "Line3D", "Arc3D", "Circle3D", etc.

                # Basic edge info
                edge_info = {
                    "index": i,
                    "geometryType": geometryType,
                    "length": edge.length
                }

                # 1) Collect bounding box data
                bb = edge.boundingBox
                if bb:
                    edge_info["boundingBox"] = {
                        "minPoint": [bb.minPoint.x, bb.minPoint.y, bb.minPoint.z],
                        "maxPoint": [bb.maxPoint.x, bb.maxPoint.y, bb.maxPoint.z]
                    }

                # 2) Collect geometry-specific data
                if isinstance(geom, adsk.core.Line3D):
                    # For finite lines, startPoint and endPoint will be non-null.
                    startPt = geom.startPoint
                    endPt = geom.endPoint

                    # Compute direction: end - start
                    if startPt and endPt:
                        directionVec = adsk.core.Vector3D.create(
                            endPt.x - startPt.x,
                            endPt.y - startPt.y,
                            endPt.z - startPt.z
                        )
                        edge_info["geometryData"] = {
                            "startPoint": [startPt.x, startPt.y, startPt.z],
                            "endPoint": [endPt.x, endPt.y, endPt.z],
                            "direction": [directionVec.x, directionVec.y, directionVec.z]
                        }
                    else:
                        # If the line is infinite (rare in typical Fusion designs),
                        # the start/endPoints might be None.
                        # You could call getData(...) here if needed.
                        edge_info["geometryData"] = {
                            "startPoint": None,
                            "endPoint": None,
                            "direction": None
                        }

                elif isinstance(geom, adsk.core.Arc3D):
                    centerPt = geom.center
                    normalVec = geom.normal
                    edge_info["geometryData"] = {
                        "centerPoint": [centerPt.x, centerPt.y, centerPt.z],
                        "normal": [normalVec.x, normalVec.y, normalVec.z],
                        "radius": geom.radius,
                        "startAngle": geom.startAngle,
                        "endAngle": geom.endAngle
                    }

                elif isinstance(geom, adsk.core.Circle3D):
                    centerPt = geom.center
                    normalVec = geom.normal
                    edge_info["geometryData"] = {
                        "centerPoint": [centerPt.x, centerPt.y, centerPt.z],
                        "normal": [normalVec.x, normalVec.y, normalVec.z],
                        "radius": geom.radius
                    }

                elif isinstance(geom, adsk.core.Ellipse3D):
                    centerPt = geom.center
                    normalVec = geom.normal
                    edge_info["geometryData"] = {
                        "centerPoint": [centerPt.x, centerPt.y, centerPt.z],
                        "normal": [normalVec.x, normalVec.y, normalVec.z],
                        "majorRadius": geom.majorRadius,
                        "minorRadius": geom.minorRadius
                    }

                elif isinstance(geom, adsk.core.NurbsCurve3D):
                    # NURBS curves can be more complex:
                    # store some minimal data; adjust as needed
                    edge_info["geometryData"] = {
                        "isNurbs": True,
                        "degree": geom.degree,
                        "controlPointCount": geom.controlPointCount
                    }

                edge_data_list.append(edge_info)

            # Return the collected info in JSON format
            #return json.dumps(edge_data_list, indent=4)
            return json.dumps(edge_data_list)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()

    def list_faces_in_body(self, component_name: str="comp1", body_name: str = "Body1") -> str:
        """
        {
            "name": "list_faces_in_body",
            "description": "Generates a list of all faces in the specified BRep body. Returns face data in JSON format that can be used for future operations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "component_name": {
                        "type": "string",
                        "description": "The name of the component in the current design containing the body."
                    },
                    "body_name": {
                        "type": "string",
                        "description": "The name of the target body whose faces will be listed."
                    }
                },
                "required": ["component_name", "body_name"],
                "returns": {
                    "type": "string",
                    "description": "A JSON array of face information. Each element contains keys such as 'index', 'surfaceType', 'area', and 'boundingBox'."
                }
            }
        }
        """

        try:
            app = adsk.core.Application.get()
            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            design = adsk.fusion.Design.cast(product)

            # Find the target component by name (assuming you have a local helper method).
            targetComponent, errors = self._find_component_by_name(component_name)
            if not targetComponent:
                return errors

            body, errors = self._find_body_by_name(targetComponent, body_name)
            if not body:
                return errors

            faces = body.faces
            face_data_list = []

            for i, face in enumerate(faces):
                geom = face.geometry
                surface_type = type(geom).__name__  # e.g., "Plane", "Cylinder", "Cone", "Sphere", "Torus", "NurbsSurface"

                # Store basic face info
                face_info = {
                    "index": i,
                    "surfaceType": surface_type,
                    "area": face.area
                }

                # Collect bounding box data for the face (if available)
                bb = face.boundingBox
                if bb:
                    face_info["boundingBox"] = {
                        "minPoint": [bb.minPoint.x, bb.minPoint.y, bb.minPoint.z],
                        "maxPoint": [bb.maxPoint.x, bb.maxPoint.y, bb.maxPoint.z]
                    }

                # Collect geometry-specific data
                geometry_data = {}
                if isinstance(geom, adsk.core.Cylinder):
                    # Cylindrical face
                    axis = geom.axis
                    origin = geom.origin
                    geometry_data = {
                        "axisVector": [axis.x, axis.y, axis.z],
                        "origin": [origin.x, origin.y, origin.z],
                        "radius": geom.radius
                    }

                elif isinstance(geom, adsk.core.Sphere):
                    # Spherical face
                    center = geom.center
                    geometry_data = {
                        "center": [center.x, center.y, center.z],
                        "radius": geom.radius
                    }

                elif isinstance(geom, adsk.core.Torus):
                    # Torus face
                    center = geom.center
                    axis = geom.axis
                    geometry_data = {
                        "center": [center.x, center.y, center.z],
                        "axisVector": [axis.x, axis.y, axis.z],
                        "majorRadius": geom.majorRadius,
                        "minorRadius": geom.minorRadius
                    }

                elif isinstance(geom, adsk.core.Cone):
                    # Conical face
                    axis = geom.axis
                    origin = geom.origin
                    geometry_data = {
                        "axisVector": [axis.x, axis.y, axis.z],
                        "origin": [origin.x, origin.y, origin.z],
                        "halfAngle": geom.halfAngle
                    }

                elif isinstance(geom, adsk.core.NurbsSurface):
                    # Nurbs-based face
                    geometry_data = {
                        "isNurbsSurface": True,
                        "uDegree": geom.degreeU,
                        "vDegree": geom.degreeV,
                        "controlPointCountU": geom.controlPointCountU,
                        "controlPointCountV": geom.controlPointCountV
                    }

                if geometry_data:
                    face_info["geometryData"] = geometry_data

                face_data_list.append(face_info)

            # Convert the collected face data to a JSON string
            return json.dumps(face_data_list, indent=4)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()

    def list_all_available_appearances(self) -> str:
        """
        {
            "name": "list_all_available_appearances",
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
            for i in range(local_appearances.count):
                appearance = local_appearances.item(i)
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
            for i in range(material_libs.count):
                library = material_libs.item(i)
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
            #return json.dumps(appearance_list, indent=4)
            return json.dumps(appearance_list)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()



    ######====================  old ====================######
    def _list_occurrence_tree(self) -> str:
        """
        {
          "name": "list_occurrence_tree",
          "description": "Generates a JSON representation of the Fusion 360 browser tree, showing occurrences nested inside their parent occurrences.",
          "parameters": {
            "type": "object",
            "properties": {
            },
            "required": [],
            "returns": {
              "type": "string",
              "description": "A JSON array of top-level occurrences. Each occurrence has a 'name', 'componentName', and 'children'."
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
            root_comp = design.rootComponent

            def gather_occurrences(occ_list: adsk.fusion.OccurrenceList) -> list:
                """
                Recursively build a list of dict objects representing
                each occurrence, including nested children occurrences.
                """
                result = []
                for i in range(occ_list.count):
                    occ = occ_list.item(i)
                    children_data = gather_occurrences(occ.childOccurrences)

                    occ_data = {
                        "occurrenceName": occ.name,
                        #"componentName": occ.component.name if occ.component else None,
                    }

                    if len(children_data) != 0:
                        occ_data["children"] = children_data

                    result.append(occ_data)

                return result

            # Gather the top-level occurrences from the root component
            tree_data = gather_occurrences(root_comp.occurrences)

            # Convert to JSON and return
            return json.dumps(tree_data, indent=2)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()

