import inspect
import adsk.core
import adsk.fusion
import adsk.cam
from adsk.fusion import RigidGroup
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
import importlib
from ... import config
from ...lib import fusion360utils as futil

# send info to html palette
from .shared import ToolCollection


def print(string):
    """redefine print for fusion env"""
    futil.log(str(string))
print(f"RELOADED: {__name__.split("%2F")[-1]}")




class SQL(ToolCollection):

    def get_error_hash(self, errors_dict, error_str):

        #error_hash = f"error_id_" + self.hash_string_to_fixed_length(error_str, 5)

        n_errors = len(errors_dict.keys())

        rev_errors_dict = {v:k for k,v in errors_dict.items()}

        existing_error = rev_errors_dict.get(error_str, None)

        if existing_error is None:
            errors_dict[f"error_{n_errors}"] = error_str

        error_hash = rev_errors_dict.get(error_str)

        return errors_dict, error_hash


    def __init__(self, ent_dict):
        super().__init__(ent_dict)


        self.SQL_PATTERN = re.compile(
            r"(?i)^\s*"
            r"(?:"
            # -----------------------------------------------------------
            # 1) SELECT statement
            # -----------------------------------------------------------
            r"SELECT\s+(?P<attributes>[\w\s,\.]+)\s+"
            r"FROM\s+(?P<objectType>\w+)"
            # optional WHERE with multiple conditions
            r"(?:\s+WHERE\s+(?P<selectWhere>"
              # Each condition: <attrName> [NOT ]? (LIKE|=|<|>|<=|>=|IN)
              # value can be:
              #   - a single-quoted string
              #   - numeric
              #   - boolean
              #   - parenthetical list for IN: ( 'foo', 10, true, ... )
              r"(?:[\w\.]+\s+(?:NOT\s+)?(?:LIKE|=|<=|>=|<|>|IN)\s+"
              r"(?:'[^']*'|[+-]?\d+(?:\.\d+)?|true|false"
              r"|\(\s*(?:'[^']*'|[+-]?\d+(?:\.\d+)?|true|false)(?:\s*,\s*(?:'[^']*'|[+-]?\d+(?:\.\d+)?|true|false))*\s*\)"
              r"))"
              r"(?:\s+(?:AND|OR)\s+[\w\.]+\s+(?:NOT\s+)?(?:LIKE|=|<=|>=|<|>|IN)\s+"
              r"(?:'[^']*'|[+-]?\d+(?:\.\d+)?|true|false"
              r"|\(\s*(?:'[^']*'|[+-]?\d+(?:\.\d+)?|true|false)(?:\s*,\s*(?:'[^']*'|[+-]?\d+(?:\.\d+)?|true|false))*\s*\)"
              r"))*"
            r"))?"
            # optional ORDER BY <attr> [ASC|DESC]
            r"(?:\s+ORDER\s+BY\s+(?P<orderAttr>[\w\.]+)"
            r"(?:\s+(?P<orderDir>ASC|DESC))?"
            r")?"
            # optional LIMIT
            r"(?:\s+LIMIT\s+(?P<limit>\d+))?"
            # optional OFFSET
            r"(?:\s+OFFSET\s+(?P<offset>\d+))?"

            r"|"

            # -----------------------------------------------------------
            # 2) UPDATE statement
            # -----------------------------------------------------------
            r"UPDATE\s+(?P<updateObjectType>\w+)"
            # setClause: lazy capture until WHERE|LIMIT|OFFSET or end
            r"\s+SET\s+(?P<setClause>[\w\s,=.'%\-\(\)\:\+0-9\.truefals]+?(?=\s+(?:WHERE|LIMIT|OFFSET)|$))"

            # optional WHERE for update
            r"(?:\s+WHERE\s+(?P<updateWhere>"
              # same condition pattern as above
              r"(?:[\w\.]+\s+(?:NOT\s+)?(?:LIKE|=|<=|>=|<|>|IN)\s+"
              r"(?:'[^']*'|[+-]?\d+(?:\.\d+)?|true|false"
              r"|\(\s*(?:'[^']*'|[+-]?\d+(?:\.\d+)?|true|false)(?:\s*,\s*(?:'[^']*'|[+-]?\d+(?:\.\d+)?|true|false))*\s*\)"
              r"))"
              r"(?:\s+(?:AND|OR)\s+[\w\.]+\s+(?:NOT\s+)?(?:LIKE|=|<=|>=|<|>|IN)\s+"
              r"(?:'[^']*'|[+-]?\d+(?:\.\d+)?|true|false"
              r"|\(\s*(?:'[^']*'|[+-]?\d+(?:\.\d+)?|true|false)(?:\s*,\s*(?:'[^']*'|[+-]?\d+(?:\.\d+)?|true|false))*\s*\)"
              r"))*"
            r"))?"
            r"(?:\s+LIMIT\s+(?P<updateLimit>\d+))?"
            r"(?:\s+OFFSET\s+(?P<updateOffset>\d+))?"

            r")\s*$"
        )

        """
        Explanation:

        1) We add "|IN" in the operator set. That means the user can do:
           "attrName IN (val1, val2, ...)" or "attrName NOT IN ( ... )"

        2) For the value after "IN", we allow a parenthetical list:
           \( 
             <singleValue> (string, number, bool) 
             (,\s*<singleValue>)*
           \)
           This is e.g. "( 'foo', 10, true )"

        3) We repeat this pattern in:
           - the first condition
           - the subsequent conditions (the part with (?:\s+(?:AND|OR)\s+...)* )
           - the updateWhere portion as well.

        4) If the operator is "IN" or "NOT IN", then the user must supply a parenthetical list. 
           If they do something like "IN 'foo'", that won't match. They need "IN ('foo')".

        5) The rest (ORDER BY, LIMIT, OFFSET, multiple AND/OR conditions, etc.) is the same.

        6) On the execution side, you'll parse the condition. If operator is "IN" or "NOT IN",
           you'll parse the parenthetical list, e.g. "('foo', 10, true)" => a list of [ "foo", 10, True ]
           then do membership checks: 
              if "IN",  objVal in that list
              if "NOT IN", objVal not in that list
        """


        self.CONDITION_PATTERN = re.compile(
            r"(?i)^\s*"
            r"([\w\.]+)"                          # Group(1): the attribute name (e.g. "component.name")
            r"\s*(?P<maybeNot>NOT\s+)?"
            r"(?P<baseOp>LIKE|=|<=|>=|<|>|IN)"    # the operator (e.g. LIKE, =, <=, etc.)
            r"\s*"                                # allow zero or more spaces after the operator
            r"(?:"                                # start of the value group
              # Option 1: single-quoted string
              r"'(?P<strVal>[^']*)'"
              r"|"
              # Option 2: numeric literal
              r"(?P<numVal>[+-]?\d+(?:\.\d+)?)(?![^'])"
              r"|"
              # Option 3: boolean
              r"(?P<boolVal>true|false)"
              r"|"
              # Option 4: parenthesized list => e.g. ( 'foo', 10, true )
              r"\(\s*(?P<inList>[^)]*)\)"
            r")"
            r"\s*$"
        )

        self.ASSIGN_PATTERN =  re.compile(
            r"(?i)^\s*"
            r"([\w\.]+)\s*"                       # attribute (possibly "component.name")
            r"=\s*"                                # equals sign with optional spaces around
            r"(?:"
              r"'(?P<strVal>[^']*)'"              # single-quoted string => group 'strVal'
              r"|(?P<numVal>[+-]?\d+(?:\.\d+)?)"  # numeric => group 'numVal'
              r"|(?P<boolVal>true|false)|"         # boolean => group 'boolVal'
              r"\(\s*(?P<inList>[^)]*)\)"        # everything inside parentheses => group "inList"
            r")"
            r"\s*$"
        )

        self.obj_mapping = {
            "Component": {
                "Sketch": "sketches",
            },
            "Occurrence": {
                "BRepBody": "bRepBodies",
            },
        }

        self.object_dict = self.document_objects()


    # TODO rename, maybe combine with other function of the same name
    def describe_fusion_classes_2(self, class_names: list = ["Sketch"]) -> str:
        """
        {
          "name": "describe_fusion_classes",
          "description": "Accepts an array of possible Fusion 360 class names (with or without full path) and returns a JSON object describing each class's methods, attributes, and basic parameter info, including an expected object type for each property if available.",
          "parameters": {
            "type": "object",
            "properties": {
              "class_names": {
                "type": "array",
                "description": "List of classes to introspect. E.g. ['Sketch', 'adsk.fusion.ExtrudeFeature']. If no module is specified, tries adsk.fusion then adsk.core.",
                "items": { "type": "string" }
              }
            },
            "required": ["class_names"],
            "returns": {
              "type": "string",
              "description": "A JSON object mapping each requested class name to method and attribute data (including expected object types) or an error."
            }
          }
        }
        """
        all_arg_objects = set()

        try:
            if not class_names or not isinstance(class_names, list):
                return json.dumps({"error": "class_names must be a non-empty list of strings"})

            def import_class_from_path(path: str):
                """
                Attempt to import something like 'adsk.fusion.Sketch'.
                Returns (cls, None) if successful, or (None, errorString) if failed.
                """
                tokens = path.split(".")
                if len(tokens) < 2:
                    return None, f"Invalid class path: '{path}'."
                mod_str = ".".join(tokens[:-1])
                cls_str = tokens[-1]
                try:
                    mod = importlib.import_module(mod_str)
                except ModuleNotFoundError:
                    return None, f"Could not import module '{mod_str}'."
                cls = getattr(mod, cls_str, None)
                if cls is None:
                    return None, f"Class '{cls_str}' not found in '{mod_str}'."
                return cls, None

            exclude_list = [
                "cast", "classType", "__init__", "__del__", "thisown",
                "revisionId", "dataComponent", "decals", "activeSheetMetalRule",
                "allAsBuiltJoints", "allJointOrigins", "allJoints", "allOccurrences",
                "allTangentRelationships", "attributes", "canvases", "findBRepUsingRay",
                "internalCommand", "createThumbnail","allOccurrencesByComponent",
                "occurrencesByComponent", "configurationRow", "configuredDataFile",
                "switchConfiguration", "setAsBallJointMotion", "setAsCylindricalJointMotion",
                "setAsPinSlotJointMotion","setAsPlanarJointMotion", "setAsRevoluteJointMotion",
                "setAsRigidJointMotion", "createForAssemblyContext" , "meshManager", "findByTempId",
                "convert", "createSpunProfile", "createSpunProfileInput", "partNumber",
                "createFlatPattern", "saveCopyAs", "replace", "setAsSliderJointMotion",
                "importSVG", "include", "redefine" , "projectCutEdges", "project", "projectToSurface",
                "moveToComponent", "isComputeDeferred", "intersectWithSketchPlane", "isValid", "trim",
                "lumps","copyTo", "createBRepEdgeProfile", "documentReference", "getPhysicalProperties",
                "setCenterlineState", "findBRepUsingPoint", "createOpenProfile"


            ]  # skip internal

            def describe_method(py_callable):
                """
                Attempt to parse signature with inspect.signature,
                then return { params: [...], doc: '' }.
                """
                # Attempt signature
                try:
                    sig = inspect.signature(py_callable)
                except ValueError:
                    sig = None

                params_info = []
                if sig:
                    for param_name, param in sig.parameters.items():
                        if param_name == "self":
                            continue

                        default_val = None if param.default is param.empty else param.default
                        annotation_str = None if param.annotation is param.empty else str(param.annotation)
                        if isinstance(annotation_str, str):
                            annotation_str = annotation_str.replace("\n", " ")

                        all_arg_objects.add(annotation_str)

                        params_info.append(f"{param_name}:{annotation_str}")

                doc_str = inspect.getdoc(py_callable) or ""


                return params_info

            def gather_class_info(cls):
                """
                Gather info on methods (callables) and attributes (non-callable) from the class.
                Returns a dict with 'methods' and 'attributes', including 'expectedObjectType' for attributes if possible.
                """
                cls_info = {
                    "methods": {},
                    "attributes": {}
                }

                # 1) Gather methods
                #   isfunction => pure Python function
                methods_found = inspect.getmembers(cls, predicate=inspect.isfunction)
                #   ismethoddescriptor => some C++ extension or property
                descriptors = inspect.getmembers(cls, predicate=inspect.ismethoddescriptor)

                combined_method_members = dict(methods_found)
                for name, desc in descriptors:
                    if name not in combined_method_members:
                        combined_method_members[name] = desc

                for name, func_obj in combined_method_members.items():
                    if name[0] == "_" or name in exclude_list:
                        continue
                    cls_info["methods"][name] = describe_method(func_obj)

                # 2) Gather all members, separate out attributes
                #   We'll skip private, skip known methods
                all_members = inspect.getmembers(cls)
                known_methods = set(combined_method_members.keys())

                for name, member_obj in all_members:
                    if name[0] == "_" or name in exclude_list:
                        continue
                    if name in known_methods:
                        continue  # we've described it as a method

                    # If not callable => treat as attribute
                    if not callable(member_obj):

                        attr_data = None

                        # Attempt to see if this is a property descriptor
                        # If so, we might be able to get a return annotation from fget
                        if inspect.isdatadescriptor(member_obj):
                            # Some descriptors may have .fget
                            fget = getattr(member_obj, 'fget', None)
                            if fget and callable(fget):
                                try:
                                    fget_sig = inspect.signature(fget)
                                    # If there's a return annotation
                                    if fget_sig.return_annotation is not inspect.Signature.empty:

                                        if ":" in fget_sig.return_annotation:
                                            object_type_str = fget_sig.return_annotation.split(":")[-1].strip(">").strip()
                                        else:
                                            object_type_str = fget_sig.return_annotation


                                        #attr_data["objectType"] = object_type_str

                                        all_arg_objects.add(object_type_str)
                                        attr_data = object_type_str

                                except ValueError:
                                    pass

                        # If we still don't have expectedObjectType, fallback to type
                        if not attr_data:
                            attr_data = member_obj.__class__.__name__

                        cls_info["attributes"][name] = attr_data

                return cls_info

            results = {}

            for class_name in class_names:
                # If there's a dot, assume it's a full path (like adsk.fusion.Sketch).
                # Otherwise, try adsk.fusion.class_name, then adsk.core.class_name
                if "." in class_name:
                    cls, err = import_class_from_path(class_name)
                    if err:
                        results[class_name] = {"error": err}
                        continue
                    results[class_name] = gather_class_info(cls)
                else:
                    # Try adsk.fusion.class_name
                    fusion_path = f"adsk.fusion.{class_name}"
                    cls, err = import_class_from_path(fusion_path)
                    if not err and cls:
                        data = gather_class_info(cls)
                        #data["resolvedPath"] = fusion_path
                        results[class_name] = data
                        continue

                    # Then try adsk.core.class_name
                    core_path = f"adsk.core.{class_name}"
                    cls2, err2 = import_class_from_path(core_path)
                    if not err2 and cls2:
                        data2 = gather_class_info(cls2)
                        #data2["resolvedPath"] = core_path
                        results[class_name] = data2
                        continue

                    # If both fail, store an error
                    results[class_name] = {"error": f"Could not find class '{class_name}' in adsk.fusion or adsk.core."}



            return results

        except Exception as e:
            return json.dumps({"Error": str(e)})


    def document_objects(self) -> dict:
        """
        {
          "name": "search_document_objects",
          "description": "SQL like query to get data from the Fusion 360 objects in the document",
          "parameters": {
            "type": "object",
            "properties": {
              "query_string": {
                "type": "string",
                "description": "SQL like query string."
              }
            },
            "required": ["query_string"],
          "returns": {
            "type": "string",
            "description": "A JSON like object containing matching data"
          },
          }

        }
        """

        app = adsk.core.Application.get()
        if not app:
            return "Error: Fusion 360 is not running."

        product = app.activeProduct
        if not product or not isinstance(product, adsk.fusion.Design):
            return "Error: No active Fusion 360 design found."

        design = adsk.fusion.Design.cast(product)
        root_comp = design.rootComponent

        appearances_list = app.materialLibraries.itemByName("Fusion Appearance Library").appearances
        materials_list = app.materialLibraries.itemByName("Fusion Material Library").materials

        timeline_object_list = [t for t in design.timeline]
        TimelineObjects =  adsk.core.ObjectCollection.createWithArray(timeline_object_list)

        #design.userParameters
        object_dict = {
            "Parameter": design.allParameters,
            "Occurrence": root_comp.allOccurrences,
            "Component": design.allComponents ,
            "Appearance": appearances_list,
            "Material": materials_list,
            "TimelineObject": TimelineObjects,
            "Joint": None,
            "JointOrigin": None,
            "RigidGroup": None,
            "Sketch": None,
            "BRepBody": None,
            "SketchCurve": None,
            "Profile": None,
            "SketchPoint": None
        }



        # vector object e.g JointVector have no 'count' attr, have to be handles differently

        vector_attrs = {
            "Joint": "allJoints",
            "JointOrigin": "allJointOrigins",
            "AsBuiltJoint": "allAsBuiltJoints",
            "RigidGroup": "allRigidGroups"
        }

        for obj_class, root_attr in vector_attrs.items():
            vector_list = [j for j in getattr(root_comp, root_attr)]
            object_dict[obj_class] = adsk.core.ObjectCollection.createWithArray(vector_list)




        for obj_class, obj_attrs in self.obj_mapping.items():
            for name, attr in obj_attrs.items():
                obj_lists = [getattr(ent, attr) for ent in object_dict[obj_class]]
                obj_list = [obj for l in obj_lists for obj in l ]
                object_dict[name] = adsk.core.ObjectCollection.createWithArray(obj_list)


        for k, v in object_dict.items():

            if v:
                print(f"{k}: {v.count}")
            else:
                print(f"{k}: {None}")

        return object_dict


    # TODO handle more object types, make better
    def reload_object_dict(self):
        """
        """

        # body
        obj_mapping = {
            "Component": {
                "Sketch": "sketches",
            },
            "Occurrence": {
                "BRepBody": "bRepBodies",
            },
            "Sketch": {
                "SketchCurve": "sketchCurves",
                "Profile": "profiles",
                "SketchPoint": "sketchPoints",
                "SketchDimension": "sketchDimensions"
            },
            "BRepBody": {
                "BRepEdge": "edges",
                "BRepFace": "faces",
            },
        }


        if self.index_sketch_children:
            self.obj_mapping["Sketch"] = obj_mapping["Sketch"]
        elif not self.index_sketch_children:
            if self.obj_mapping.get("Sketch"):
                self.obj_mapping.pop("Sketch")

        if self.index_brep_children:
            self.obj_mapping["BRepBody"] = obj_mapping["BRepBody"]

        elif not self.index_brep_children:
            if self.obj_mapping.get("BRepBody"):
                self.obj_mapping.pop("BRepBody")


        print(self.obj_mapping)
        self.object_dict = self.document_objects()

    def get_object_dict(self):
        if self.reload_object_index == True:
            self.object_dict = self.document_objects()
            print(f"object dict reloaded")

        return self.object_dict

    @ToolCollection.tool_call
    def get_available_classes(self):
        """
        {
          "name": "get_available_classes",
           "description": "Provides information about available classes their attributes, methods and data types. The returned object contains to sub-dictionaries: document_objects and transient_objects. The top levle keys in document_object represent the available classes for use with the 'run_sql_query' and 'call_entity_methods' functions. Each class-dict contains available attributes and methods, along with their data types. The  transient_objects dict follows the same format, but contains information about transient object classes.",

          "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
              "returns": {
                "type": "string",
                "description": "A JSON like object containing document_object data"
              }
          }

        }
        """
        # transient object
        trans_objects = [
            "Point3D",
            "Matrix3D",
            "Vector3D",
            "BoundingBox3D"
        ]
        document_object_types = self.document_objects()

        transient_objects_info =  self.describe_fusion_classes_2(trans_objects)
        document_objects_info =  self.describe_fusion_classes_2(list(document_object_types.keys()))

        return_dict = {
            "document_objects": document_objects_info,
            "transient_objects": transient_objects_info
        }


        return json.dumps(return_dict)


    def parse_where_conditions(self, where_str: str):
        """
        Splits 'where_str' on AND/OR, returning a list of condition dicts:
        [ { 'attrName': '...', 'operator': 'NOT LIKE', 'value': 'foo', 'logicOpBefore': None|'AND'|'OR' }, ... ]
        """
        if not where_str:
            return []

        tokens = re.split(r"(?i)\s+(AND|OR)\s+", where_str.strip())
        conditions = []

        # parse the first condition
        first_cond = self.parse_single_condition(tokens[0])
        if first_cond:
            first_cond["logicOpBefore"] = None
            conditions.append(first_cond)

        i = 1
        while i < len(tokens) - 1:
            logic_op = tokens[i].upper()
            cond_text = tokens[i+1]
            c = self.parse_single_condition(cond_text)
            if c:
                c["logicOpBefore"] = logic_op
                conditions.append(c)
            i += 2

        return conditions

    def parse_set_clause(self, set_clause_str: str):
        """
        e.g. "name='Housing', isLightBulbOn=true, value=10"
        => [
             { "attrName": "name", "value": "Housing" },
             { "attrName": "isLightBulbOn", "value": True },
             { "attrName": "value", "value": 10 }
           ]
        """
        parts = [p.strip() for p in set_clause_str.split(',')]
        out = []
        for p in parts:
            m = self.ASSIGN_PATTERN.match(p)
            if not m:
                return {"error": f"Unrecognized assignment: {p}"}

            attr_name = m.group(1)
            str_val   = m.group("strVal")
            num_val   = m.group("numVal")
            bool_val  = m.group("boolVal")

            if str_val is not None:
                final_val = str_val
            elif num_val is not None:
                if '.' in num_val:
                    final_val = float(num_val)
                else:
                    final_val = int(num_val)
            elif bool_val is not None:
                final_val = (bool_val.lower() == 'true')
            else:
                final_val = None

            out.append({"attrName": attr_name, "value": final_val})

        return out

    def parse_single_condition(self,cond_text: str):
        """
        Example usage to parse a single condition string like:
          "name='body1'"
          "value >= 10"
          "component.nameNOTLIKE'%temp%'"
          "flagNOTIN(true,false,'maybe')"
        """
        m = self.CONDITION_PATTERN.match(cond_text.strip())
        if not m:
            return None

        attr_name = m.group(1)               # "name" or "component.name"
        maybe_not = m.group("maybeNot")      # e.g. "NOT " or None
        base_op   = m.group("baseOp").upper()# e.g. LIKE, =, <, >, <=, >=, IN
        str_val   = m.group("strVal")        # string content if user typed 'foo'
        num_val   = m.group("numVal")        # numeric if user typed 3.14 or 10
        bool_val  = m.group("boolVal")       # "true" or "false" if user typed that
        in_list   = m.group("inList")        # e.g. "10,'foo',true" inside parentheses

        # Combine "NOT" with the base operator if present
        if maybe_not:
            operator = (maybe_not.strip() + base_op).upper()  # e.g. "NOT LIKE", "NOT IN"
        else:
            operator = base_op

        # Decide final value
        value = None
        if in_list is not None:
            # parse the in_list e.g. "10, 'foo', true"
            value = parse_in_list(in_list)
        elif str_val is not None:
            value = str_val
        elif num_val is not None:
            # interpret as float or int
            if '.' in num_val:
                value = float(num_val)
            else:
                value = int(num_val)
        elif bool_val is not None:
            value = (bool_val.lower() == 'true')

        return {
            "attrName": attr_name,
            "operator": operator,  # e.g. "LIKE", "NOT LIKE", "IN", "NOT IN", "<", etc.
            "value": value         # either a single value or list (for IN)
        }


    def parse_in_list(self, list_str: str):
        """
        A simple function that splits a parenthesized list on commas
        and interprets each item as a string, number, or bool.
        e.g. "10, 'foo', true" => [10, "foo", True]
        """
        items = [x.strip() for x in list_str.split(',')]
        out = []
        for it in items:
            # if it is quoted => string
            m_str = re.match(r"^'(.*)'$", it)
            if m_str:
                out.append(m_str.group(1))
                continue

            # if numeric
            m_num = re.match(r"^[+-]?\d+(?:\.\d+)?$", it, re.IGNORECASE)
            if m_num:
                if '.' in it:
                    out.append(float(it))
                else:
                    out.append(int(it))
                continue

            # if bool
            if it.lower() in ("true", "false"):
                out.append(it.lower() == "true")
                continue

            # fallback => raw
            out.append(it)
        return out

    def match_object_against_conditions(self, obj, conditions):
        """
            Checks whether 'obj' satisfies the list of 'conditions', each of which is
            a dict with:
              {
                "attrName": str,             # e.g. "name" or "appearance.name"
                "operator": str,             # e.g. "LIKE", "NOT LIKE", "=", or "NOT ="
                "value": str,                # e.g. "%gear%"
                "logicOpBefore": str|None    # "AND", "OR", or None for the first condition
              }

            The function returns True if 'obj' meets the entire set of conditions
            when chained by AND/OR logic in the specified order, or False otherwise.

        """
        def condition_matches(obj, cond):
            """
                E.g. cond might be:
                  { "attrName": "name", "operator": "LIKE", "value": "%gear%" }
                or
                  { "attrName": "name", "operator": "NOT LIKE", "value": "_oot" }
                We'll interpret % as multi-char, _ as single-char wildcard in a naive manner.
            """

            operator = cond["operator"].upper()
            value = cond["value"]
            attr_name = cond["attrName"]

            # get object atribute for comparison
            attr_val, errors = self.get_sub_attr(obj, attr_name)

            #print(f"operator: {operator},  val: {value},  attr_name: {attr_name}, attr_val: {attr_val}")

            if errors:
                return errors

            if operator == "IN":
                return attr_val in value

            elif operator == "NOT IN":
                return attr_val not in value

            elif operator == "LIKE":
                return do_like_compare(str(attr_val), value, negate=False)

            elif operator == "NOT LIKE":
                return do_like_compare(str(attr_val), value, negate=True)

            elif operator == "=":
                return (attr_val == value)

            elif operator == "NOT =":
                return (attr_val != value)

            elif operator == "<":
                return (attr_val < value)

            elif operator == "<=" or operator == "NOT >":
                return (attr_val <= value)

            elif operator == ">":
                return (attr_val > value)

            elif operator == ">=" or operator == "NOT <":
                return (attr_val >= value)

            else:
                return False


        def do_like_compare(actual_str, pattern_str, negate=False):
            """
            Interprets pattern_str as having '%' for multi-char wildcard and '_' for single-char wildcard.
            We'll convert them to python regex equivalents:
               % -> .*
               _ -> .
            Then do a case-insensitive search. If 'negate' is True, we invert the result.
            """

            # Step 1) Escape everything so we match literally except for the wildcards we'll replace
            escaped = re.escape(str(pattern_str))

            # Step 2) Replace the escaped versions of '%' and '_' with the desired regex pattern.
            # Because re.escape('%') => '\%', re.escape('_') => '\_'
            # so we find those sequences in 'escaped' and replace them with .*, .
            # e.g. "gear\%" => "gear.*"
            # e.g. "foo\_" => "foo."
            # We do the replacements in that order so we don't inadvertently re-replace something.
            escaped = escaped.replace(r'%', '.*')
            escaped = escaped.replace(r'_', '.')

            # We'll do a full search ignoring case
            match_found = bool(re.search(escaped, actual_str, re.IGNORECASE))
            return (not match_found) if negate else match_found


        # We'll iterate conditions in order, combining them with AND/OR logic
        overall_result = None

        for i, cond in enumerate(conditions):

            attr_name = cond["attrName"]

            val, errors = self.get_sub_attr(obj, attr_name)
            if errors != None:
                return None, errors

            cRes = condition_matches(obj, cond)

            if i == 0:
                # first condition => just set overall_result to cRes
                overall_result = cRes
            else:
                logic_op = cond.get("logicOpBefore", "AND").upper()
                if logic_op == "AND":
                    overall_result = overall_result and cRes
                elif logic_op == "OR":
                    overall_result = overall_result or cRes
                else:
                    # if somehow we get an unknown operator, fallback to AND
                    overall_result = overall_result and cRes

        # If no conditions, default to True (no filter)
        if overall_result is None:
            return True, None

        return overall_result, None

    def apply_assignments(self, obj, assignments):
        """Set values  """
        updated_something = False

        BOOL_MAP = {
            "true": True,
            "false": False,
            "1": True,
            "0": False
        }

        details = {}
        for assign in assignments:
            attr_name = assign["attrName"]
            new_val = assign["value"]

            # get current val check errors
            current_val, errors = self.get_sub_attr(obj, attr_name)
            # use current val typ to validate
            current_type = type(current_val)

            if isinstance(current_val, bool):

                # convert str "true" "false" to bool
                if isinstance(new_val, str):
                    # check if lower-cased value is in BOOL_MAP
                    val_lower = new_val.lower()
                    if val_lower in BOOL_MAP:
                        new_val = BOOL_MAP[val_lower]  # a Python bool

                # convert 0, 1 to bool
                if isinstance(new_val, int):
                    if new_val == 0:
                        new_val = False
                    elif new_val == 1:
                        new_val = True


            elif isinstance(new_val, str):
                hash_obj = self.ent_dict.get(new_val, None)
                if hash_obj != None:
                    new_val = hash_obj


            if errors:
                details[attr_name] = f"{errors}"
            else:
                success, errors = self.set_sub_attr(obj, attr_name, new_val )
                details[attr_name] = f"new_val: {new_val}"
                updated_something = True

        return {
            "updated": updated_something,
            "details": details
        }

    @ToolCollection.tool_call
    def run_sql_query(self, query_str: str = "SELECT name,entityToken FROM Occurrence WHERE name LIKE 'screw'") -> str:
        """
            {
              "name": "run_sql_query",
              "description": "Executes a naive, SQL-like query on the current Fusion 360 design. Supports standard SQL syntax: SELECT, UPDATE, SET, FROM, WHERE, LIKE, IN, AND, OR, ORDER BY, ASC, DESC, LIMIT, OFFSET, for the following object: [Occurrence, Component, BRepBody, Sketch, Joint, JointOrigin, SketchLine]. Supports . syntax to access sub attributes.Examples:\
            SELECT name,entityToken FROM Component\
            Return the name an entityTokens for all components in the design\
            SELECT appearance.name,entityToken FROM Occurrence WHERE appearance.name LIKE '%Aluminum%'\
            returns the name of the appearance object for all Occurrence objects whose appearance name contains the string 'Aluminum'",
              "parameters": {
                "type": "object",
                "properties": {
                  "query_str": {
                    "type": "string",
                    "description": "A simplified SQL-like query, e.g. SELECT name, entityToken FROM Occurrence WHERE name LIKE 'screw'"
                  }
                },
                "required": ["query_string"],
                "returns": {
                  "type": "string",
                  "description": "JSON array with the requested attributes of matching objects or an error message"
                }
              }
            }
        """

        try:



            if not query_str or not isinstance(query_str, str):
                return json.dumps({"error": "query_str must be a non-empty string"})

            # 1) Match against the big pattern
            match = self.SQL_PATTERN.match(query_str.strip())
            if not match:
                return json.dumps({"error": "Invalid or unsupported SQL query"})

            # Distinguish SELECT vs. UPDATE
            # SELECT target object
            object_type = match.group("objectType")

            if object_type:
                statement_type = "SELECT"
                attributes_str = match.group("attributes")  # for SELECT
                where_str = match.group("selectWhere")
                limit_str = match.group("limit")
                offset_str = match.group("offset")
            else:
                # UPDATE target object
                statement_type = "UPDATE"
                object_type = match.group("updateObjectType")  # for UPDATE
                set_clause_str = match.group("setClause")
                where_str = match.group("updateWhere")
                limit_str = match.group("updateLimit")
                offset_str = match.group("updateOffset")

            order_attr = match.group("orderAttr")  # might be None if no ORDER BY
            order_dir = match.group("orderDir")   # might be "ASC", "DESC", or None

            limit_val = int(limit_str) if limit_str else None
            offset_val = int(offset_str) if offset_str else None

            # parse conditions in update_where_str => a list of condition dict
            conditions = self.parse_where_conditions(where_str)

            # gather objects of type update_object_type

            # TODO object dict created in __init__, needs to update during runtime
            #doc_objs = self.document_objects()
            doc_objs = self.get_object_dict()
            all_objs = doc_objs.get(object_type, None)
            # validate object_type

            return_dict = {
                "statementType": statement_type,
                "objectType": object_type,
            }

            errors_dict = {}

            if all_objs is None:
                return f"Error: '{object_type}' is not a valid object type, valid objects are: {list(doc_objs.keys())} "
            # handle no objects
            if all_objs.count == 0:
                return f"Error: No '{object_type}' objects in the current design"

            # check ORDER BY attribute is valid
            if order_attr != None:
                _, errors = self.get_sub_attr(all_objs.item(0), order_attr)
                # if ORDER BY fields fails return objects un-ordered
                if errors:
                    error_dict, error_hash = self.get_error_hash(errors_dict, errors)
                    order_attr = None

            # filter objects them
            filtered_objs = []
            for index, o in enumerate(all_objs):
                match, errors = self.match_object_against_conditions(o, conditions)

                # TODO an object attribute whose usual type is another fusion object may be None
                # should return a succinct error
                if errors != None:
                    error_dict, error_hash = self.get_error_hash(errors_dict, errors)
                    #print(f"Error: objet match")
                    continue
                    #return errors

                if match == True:
                    obj_dict = {
                        'obj': o,
                    }
                    if order_attr != None:

                        sort_val, errors = self.get_sub_attr(o, order_attr)

                        # if no value for order by field leave blank
                        if sort_val is None:
                            error_dict, error_hash = self.get_error_hash(errors_dict, errors)
                        else:
                            obj_dict["sort_val"] = sort_val

                    filtered_objs.append(obj_dict)


            # sort
            if order_attr != None:
                reverse = False

                if order_dir == "DESC":
                    reverse = True

                # TODO may need to handle if some None in order by fields
                #filtered_objs = [o for o in filtered_objs if o != None]
                #print(order_attr)
                #print(filtered_objs)
                filtered_objs = sorted(filtered_objs, key=lambda item: item["sort_val"], reverse=reverse)

            # convert back to list of objects
            filtered_objs = [i["obj"] for i in filtered_objs]

            # apply offset/limit
            if offset_val:
                if offset_val < len(filtered_objs):
                    filtered_objs = filtered_objs[offset_val:]
                else:
                    filtered_objs = []
            if limit_val and limit_val < len(filtered_objs):
                filtered_objs = filtered_objs[:limit_val]


            # If we have update_object_type => it's an UPDATE statement
            # otherwise, we treat it as SELECT
            if statement_type == "UPDATE":
                # 2) We parse the setClause into assignments: e.g. "name='Gear', appearance.name='Steel'"
                # TODO
                assignments = self.parse_set_clause(set_clause_str)

                if "error" in assignments:
                    error_dict, error_hash = self.get_error_hash(errors_dict, assignments)
                    #return json.dumps({"error": f"Error in SET clause: {assignments['error']}"})

                # 6) apply assignments
                updated_count = 0
                assignment_results = {}
                for obj in filtered_objs:
                    # we apply the set of assignments
                    update_result = self.apply_assignments(obj, assignments)
                    if update_result["updated"]:
                        updated_count += 1
                    assignment_results[self.set_obj_hash(obj)] = update_result["details"]

                return_dict.update( {
                    "foundCount": len(filtered_objs),
                    "updatedCount": updated_count,
                })


            else:
                # SELECT statement
                # parse the attributes
                attribute_list = [a.strip() for a in attributes_str.split(",")]

                # check if all attributes exist
                for attr_name in attribute_list:
                    if len(filtered_objs) == 0:
                        break
                        #return json.dumps(return_dict)

                    val, errors = self.get_sub_attr(filtered_objs[0], attr_name)
                    if errors != None:

                        error_dict, error_hash = self.get_error_hash(errors_dict, errors)
                        continue

                #if len(return_dict["errors"]) > 0:
                #    return json.dumps(return_dict)

                # build result
                # for each object, we gather the requested attributes
                results = []
                for index, obj in enumerate(filtered_objs):
                    row_data = {}
                    for attr in attribute_list:

                        val, errors = self.get_sub_attr(obj, attr)
                        if errors:
                            error_dict, error_hash = self.get_error_hash(errors_dict, errors)
                            val = error_hash

                            #continue
                        if hasattr(val, "objectType"):
                            val = str(val)
                        if callable(val):
                            val = str(val)

                        row_data[attr] = val

                    results.append(row_data)

                return_dict.update({
                    "count": len(results),
                    "results": results
                })


            if len(errors_dict) != 0:
                return_dict["errors"] = errors_dict

            return json.dumps(return_dict)


        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()


class GetStateData(ToolCollection):
    """
    methods used by Realtime API to retrive state of Fusion document
    """

    @ToolCollection.tool_call
    def get_fusion_classes_detail(self, class_names: list = ["Sketch"]) -> str:
        """
        {
          "name": "get_fusion_classes_detail",
          "description": "Accepts an array of possible Fusion 360 class names (with or without full path) and returns a JSON object describing each class's methods, attributes, and basic parameter info, including an expected object type for each property if available.",
          "parameters": {
            "type": "object",
            "properties": {
              "class_names": {
                "type": "array",
                "description": "List of classes to introspect. E.g. ['Sketch', 'adsk.fusion.ExtrudeFeature']. If no module is specified, tries adsk.fusion then adsk.core.",
                "items": { "type": "string" }
              }
            },
            "required": ["class_names"],
            "returns": {
              "type": "string",
              "description": "A JSON object mapping each requested class name to method and attribute data (including expected object types) or an error."
            }
          }
        }
        """
        try:
            if not class_names or not isinstance(class_names, list):
                return json.dumps({"error": "class_names must be a non-empty list of strings"})

            def import_class_from_path(path: str):
                """
                Attempt to import something like 'adsk.fusion.Sketch'.
                Returns (cls, None) if successful, or (None, errorString) if failed.
                """
                tokens = path.split(".")
                if len(tokens) < 2:
                    return None, f"Invalid class path: '{path}'."
                mod_str = ".".join(tokens[:-1])
                cls_str = tokens[-1]
                try:
                    mod = importlib.import_module(mod_str)
                except ModuleNotFoundError:
                    return None, f"Could not import module '{mod_str}'."
                cls = getattr(mod, cls_str, None)
                if cls is None:
                    return None, f"Class '{cls_str}' not found in '{mod_str}'."
                return cls, None

            exclude_list = ["cast", "classType", "__init__", "__del__"]  # skip internal

            def describe_method(py_callable):
                """
                Attempt to parse signature with inspect.signature,
                then return { params: [...], doc: '' }.
                """
                # Attempt signature
                try:
                    sig = inspect.signature(py_callable)
                except ValueError:
                    sig = None

                params_info = []
                if sig:
                    for param_name, param in sig.parameters.items():
                        if param_name == "self":
                            continue

                        default_val = None if param.default is param.empty else param.default
                        annotation_str = None if param.annotation is param.empty else str(param.annotation)
                        if isinstance(annotation_str, str):
                            annotation_str = annotation_str.replace("\n", " ")

                        params_info.append({
                            "name": param_name,
                            "default": default_val,
                            "paramType": annotation_str
                        })

                doc_str = inspect.getdoc(py_callable) or ""


                return {
                    "params": params_info,
                    "doc": doc_str.replace("\n", " ")
                }

            def gather_class_info(cls):
                """
                Gather info on methods (callables) and attributes (non-callable) from the class.
                Returns a dict with 'methods' and 'attributes', including 'expectedObjectType' for attributes if possible.
                """
                cls_info = {
                    "methods": {},
                    "attributes": {}
                }

                # 1) Gather methods
                #   isfunction => pure Python function
                methods_found = inspect.getmembers(cls, predicate=inspect.isfunction)
                #   ismethoddescriptor => some C++ extension or property
                descriptors = inspect.getmembers(cls, predicate=inspect.ismethoddescriptor)

                combined_method_members = dict(methods_found)
                for name, desc in descriptors:
                    if name not in combined_method_members:
                        combined_method_members[name] = desc

                for name, func_obj in combined_method_members.items():
                    if name[0] == "_" or name in exclude_list:
                        continue
                    cls_info["methods"][name] = describe_method(func_obj)

                # 2) Gather all members, separate out attributes
                #   We'll skip private, skip known methods
                all_members = inspect.getmembers(cls)
                known_methods = set(combined_method_members.keys())

                for name, member_obj in all_members:
                    if name[0] == "_" or name in exclude_list:
                        continue
                    if name in known_methods:
                        continue  # we've described it as a method

                    # If not callable => treat as attribute
                    if not callable(member_obj):
                        attr_data = {
                            "doc": inspect.getdoc(member_obj).replace("\n", " ") or "",
                            "objectType": None  # We'll fill this below
                        }

                        # Attempt to see if this is a property descriptor
                        # If so, we might be able to get a return annotation from fget
                        if inspect.isdatadescriptor(member_obj):
                            # Some descriptors may have .fget
                            fget = getattr(member_obj, 'fget', None)
                            if fget and callable(fget):
                                try:
                                    fget_sig = inspect.signature(fget)
                                    # If there's a return annotation
                                    if fget_sig.return_annotation is not inspect.Signature.empty:

                                        if ":" in fget_sig.return_annotation:
                                            object_type_str = fget_sig.return_annotation.split(":")[-1].strip(">").strip()
                                        else:
                                            object_type_str = fget_sig.return_annotation


                                        attr_data["objectType"] = object_type_str
                                except ValueError:
                                    pass

                        # If we still don't have expectedObjectType, fallback to type
                        if not attr_data["objectType"]:
                            attr_data["objectType"] = member_obj.__class__.__name__

                        cls_info["attributes"][name] = attr_data

                return cls_info

            results = {}

            for class_name in class_names:
                # If there's a dot, assume it's a full path (like adsk.fusion.Sketch).
                # Otherwise, try adsk.fusion.class_name, then adsk.core.class_name
                if "." in class_name:
                    cls, err = import_class_from_path(class_name)
                    if err:
                        results[class_name] = {"error": err}
                        continue
                    results[class_name] = gather_class_info(cls)
                else:
                    # Try adsk.fusion.class_name
                    fusion_path = f"adsk.fusion.{class_name}"
                    cls, err = import_class_from_path(fusion_path)
                    if not err and cls:
                        data = gather_class_info(cls)
                        data["resolvedPath"] = fusion_path
                        results[class_name] = data
                        continue

                    # Then try adsk.core.class_name
                    core_path = f"adsk.core.{class_name}"
                    cls2, err2 = import_class_from_path(core_path)
                    if not err2 and cls2:
                        data2 = gather_class_info(cls2)
                        data2["resolvedPath"] = core_path
                        results[class_name] = data2
                        continue

                    # If both fail, store an error
                    results[class_name] = {"error": f"Could not find class '{class_name}' in adsk.fusion or adsk.core."}

            return json.dumps(results)

        except Exception as e:
            return json.dumps({"Error": str(e)})


    @ToolCollection.tool_call
    def list_document_structure(self) -> str:
        """
        {
            "name": "list_document_structure",
            "description": "Recursively searches the entire Fusion 360 design, returning a JSON structure of occurrences, bodies, sketches, joints, and joint origins in the document. Each object includes its name and entity token (if available).",
            "parameters": {
                "type": "object",
                "properties": {
                },
                "required": [],
                "returns": {
                    "type": "string",
                    "description": "A JSON representation of the entire document's structure, including entity tokens if available."
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

            # Helper function to retrieve an entity token (or None if not found)
            def get_token(obj) -> str:
                return self.set_obj_hash(obj)  # or your equivalent method


            def gather_occurrence_structure(occ: adsk.fusion.Occurrence, level=0) -> dict:
                """
                Recursively gather info about a single occurrence, including
                all bodies, sketches, joints, joint origins, and child occurrences.
                """
                comp = occ.component

                # 1) Bodies
                bodies_info = []
                for b in comp.bRepBodies:
                    bodies_info.append({
                        "name": b.name,
                        "token": get_token(b)
                    })

                # 2) Sketches
                sketches_info = []
                for sk in comp.sketches:
                    sketches_info.append({
                        "name": sk.name,
                        "token": get_token(sk)
                    })

                # 3) Joints
                # Joints can appear in various places (often root). We'll assume comp.joints are relevant here.
                joints_info = []
                for j in comp.joints:
                    # j.name is often blank, so you may store j.occurrenceOne / j.occurrenceTwo, etc.
                    joints_info.append({
                        "name": j.name,
                        "token": get_token(j)
                    })

                # 4) Joint Origins
                joint_origins_info = []
                for jo in comp.jointOrigins:
                    joint_origins_info.append({
                        "name": jo.name,
                        "token": get_token(jo)
                    })

                # 5) Child occurrences
                children_info = []
                for child_occ in occ.childOccurrences:
                    children_info.append(gather_occurrence_structure(child_occ, level-1))


                # Build this occurrence's node in the tree
                return_dict =  {
                    "occurrenceName": occ.name,
                    "occurrenceToken": get_token(occ),
                    #"componentName": comp.name,
                    "componentToken": get_token(comp),
                    "bodies": bodies_info,
                    "sketches": sketches_info,
                    "joints": joints_info,
                    "jointOrigins": joint_origins_info,
                    "children": children_info
                }


                exclude_list = []
                for k,v in return_dict.items():

                    if len(v) == 0:
                        exclude_list.append(k)


                for k in exclude_list:
                    return_dict.pop(k)

                return return_dict



            # Gather top-level occurrences from the root component
            occurrences_info = []
            for occ in root_comp.occurrences:
                occurrences_info.append(gather_occurrence_structure(occ, 0))

            # Additionally, gather bodies/sketches/joints/joint origins directly in root (if any)
            root_bodies = []
            for b in root_comp.bRepBodies:
                root_bodies.append({
                    "name": b.name,
                    "entityToken": get_token(b)
                })

            root_sketches = []
            for sk in root_comp.sketches:
                root_sketches.append({
                    "name": sk.name,
                    "entityToken": get_token(sk)
                })

            root_joints = []
            for j in root_comp.joints:
                root_joints.append({
                    "name": j.name,
                    "entityToken": get_token(j)
                })

            root_joint_origins = []
            for jo in root_comp.jointOrigins:
                root_joint_origins.append({
                    "name": jo.name,
                    "entityToken": get_token(jo)
                })

            # Build a top-level structure representing the entire design
            design_tree = {
                "rootComponentName": root_comp.name,
                "rootComponentToken": get_token(root_comp),
                "rootBodies": root_bodies,
                "rootSketches": root_sketches,
                "rootJoints": root_joints,
                "rootJointOrigins": root_joint_origins,
                "occurrences": occurrences_info
            }

            return json.dumps(design_tree)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()


    @ToolCollection.tool_call
    def get_root_component_name(self):
        """
        {
            "name": "get_root_component_name",
            "description": "Retrieves the name and entityToken of the root component in the current Fusion 360 design.",
            "parameters": {}
        }
        """
        try:
            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)

            # Access the active design
            if design:
                # Return the name of the root component
                return_d = {
                    "rootComponent_name": design.rootComponent.name,
                    "entityToken": self.set_obj_hash(design.rootComponent)
                 }

                return json.dumps(return_d)
            else:
                return None

        except Exception as e:
            return None

    #@ToolCollection.tool_call
    def get_dict(self):
        """
        {
            "name": "get_dict",
            "description": "Gets all locally avilble entityTokens and thier associated objectTypes.",
            "parameters": {
                "type": "object",
                "properties": { },
                "required": [],
                "returns": {
                    "type": "string",
                    "description": "A JSON representation of the all local entityToken, and their associated objectTypes."
                }

            }
        }
        """

        results = {}
        for k, v in self.ent_dict.items():
            results[k] = str(v.__class__.__name__)

        return json.dumps(results)



class SetStateData(ToolCollection):

    @ToolCollection.tool_call
    def call_entity_methods(self, calls_list: list = [
                   { "entityToken": "", "method_path": "", "arguments": [] }
    ]) -> str:
        """
        {
          "name": "call_entity_methods",
          "description": "Dynamically calls a method on each referenced Fusion 360 entity (by token). Each instruction has { 'entityToken': <string>, 'method_path': <string>, 'arguments': <array> }. The method is invoked with the specified arguments, returning the result or null on error.",
          "parameters": {
            "type": "object",
            "properties": {
              "calls_list": {
                "type": "array",
                "description": "A list of calls. Each is { 'entityToken': <string>, 'methodName': <string>, 'arguments': <array> }.",
                "items": {
                  "type": "object",
                  "properties": {
                    "entityToken": { "type": "string" },
                    "method_path": {
                        "type": "string",
                        "description": "The path from the entity to the method, seperated with '.' if multi part. If the method directly belongs to the entity then method path is the method name. If the method belongs to one of the entity's child objects then the method_path would be 'sub_object_name.method_name'."
                        },
                    "arguments": {
                      "type": "array",
                      "items": { "type": ["boolean","number","string","null"] },
                      "description": "A list of positional arguments to pass to the method. Type handling is minimal, so interpret carefully in the method."
                    }
                  },
                  "required": ["entityToken", "method_path", "arguments"]
                }
              }
            },
            "required": ["calls_list"],
            "returns": {
              "type": "string",
              "description": "A JSON object mapping entityToken to the method call result or null on error."
            }
          }
        }
        """

        try:
            if not calls_list or not isinstance(calls_list, list):
                return "Error: calls_list must be a non-empty list."

            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            design = adsk.fusion.Design.cast(product)

            # return value
            results = {}

            for index, call_dict in enumerate(calls_list):
                entity_token = call_dict.get("entityToken")
                method_name = call_dict.get("method_path")
                arguments = call_dict.get("arguments", [])

                results[index] = {}
                if not entity_token:
                    results[index] = f"Error: no entity token provided"
                    continue
                if not method_name:
                    results[index][entity_token]= f"Error: no method name provided for entity token: {entity_token}"
                    continue

                # top level entity
                entity = self.get_hash_obj(entity_token)

                if entity is None:
                    results[index][entity_token] = f"Error: no entity found for entity token: {entity_token}, when calling method {method_name}."
                    continue

                entity_type = entity.__class__.__name__

                method, errors = self.get_sub_attr(entity, method_name)

                if errors:
                    results[index][entity_token] = errors
                    continue


                # TODO clean this up
                # get associated object of argument passed it
                parsed_arguments = []
                for arg in arguments:

                    if isinstance(arg, str) == False:
                        parsed_arguments.append(arg)
                    else:
                        entity_arg = self.get_hash_obj(arg)
                        if entity_arg != None:
                            parsed_arguments.append(entity_arg)
                        else:
                            parsed_arguments.append(arg)


                print(parsed_arguments)
                # Attempt to call the method with the provided arguments
                ret_val = None
                new_objects = []
                try:
                    # This tries a direct call with *arguments
                    try:

                        method_ret_val = method(*parsed_arguments)

                    except Exception as e:
                        method_doc = method.__doc__.replace("    ", "").replace("\n", " ")

                        ret_val = f"Error: Method call '{method_name}' on object '{entity_type}' with arguments '{arguments}' failed:  {str(e).replace('\t', ' ')}. Method docstring: {method_doc}"


                        results[index][entity_token] = ret_val
                        continue

                    if any([ isinstance(method_ret_val, attrType) for attrType in [str, int, float, bool]] ) == False:

                        new_obj_type = method_ret_val.__class__.__name__
                        new_objects += self.object_creation_response(method_ret_val)


                        if hasattr(method_ret_val, "item") == True:
                            ret_val = f"Success: method '{method_name}' returned new '{new_obj_type}'"


                        # also return component info 
                        elif hasattr(method_ret_val, "component") == True:

                            # dont call on object lists
                            new_entity_token = self.set_obj_hash(method_ret_val)

                            new_component = method_ret_val.component
                            new_objects += self.object_creation_response(new_component)

                            new_comp_token = self.set_obj_hash(new_component)
                            ret_val = f"Success: method '{method_name}' returned new '{new_obj_type}' object with entityToken '{new_entity_token}' and new 'component' with entityToken '{new_comp_token}'"

                        else:
                            # dont call on object lists
                            new_entity_token = self.set_obj_hash(method_ret_val)
                            ret_val = f"Success: method '{method_name}' returned new '{new_obj_type}' object with entityToken '{new_entity_token}'"

                    elif method_ret_val == True:
                        ret_val = f"Success: method '{method_name}' returned: '{method_ret_val}'"
                    elif method_ret_val is None:
                        ret_val = f"Error: method '{method_name}' returned '{method_ret_val}'."
                    else:
                        ret_val = f"Success: method '{method_name}' returned value: '{method_ret_val}'"

                    results[index][entity_token] = {}
                    results[index][entity_token]["Message"] = ret_val
                    if new_objects != []:
                        results[index][entity_token]["Objects"] = new_objects


                except Exception as e:
                    ret_val = f"Error: '{e}' for method '{method_name}'"


            # Return as JSON
            return json.dumps(results)


        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()


    @ToolCollection.tool_call
    def move_occurrence(self,
                       entity_token: str = "",
                       move_position: list = [1.0, 1.0, 0.0]) -> str:
        """
        {
          "name": "move_occurrence",
          "description": "Moves the specified occurrence so that its local origin is placed at the given [x, y, z] point in centimeters.",
          "parameters": {
            "type": "object",
            "properties": {
              "entity_token": {
                "type": "string",
                "description": "Entity token representing an occurrence object"
              },
              "move_position": {
                "type": "array",
                "description": "The [x, y, z] coordinates (in centimeters) to place the component's local origin in the global coordinate system.",
                "items": { "type": "number" }
              }
            },
            "required": ["entity_token", "move_position"],
            "returns": {
              "type": "string",
              "description": "A message indicating the result of the move operation."
            }
          }
        }
        """

        try:
            results = {}
            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            design = adsk.fusion.Design.cast(product)
            root_comp = design.rootComponent
            features = root_comp.features

            # Validate the move_position format: expecting [x, y, z].
            if (not isinstance(move_position, list)) or (len(move_position) < 3):
                return "Error: move_position must be an array of [x, y, z]."

            # Extract the coordinates (in centimeters)
            x_val, y_val, z_val = move_position

            targetOccurrence = self.get_hash_obj(entity_token)
            if not targetOccurrence:
                return f"Error: No occurrence found for entity_token '{entity_token}'"
            if not isinstance(targetOccurrence, adsk.fusion.Occurrence):
                return f"Error: '{entity_token}' does not represent an Occurrence entity"

            occurrence_name = targetOccurrence.name

            # Create a transform with the translation [x_val, y_val, z_val].
            transform = targetOccurrence.transform2 #adsk.core.Matrix3D.create()

            translation = adsk.core.Vector3D.create(x_val, y_val, z_val)

            transform.translation = translation

            try:
                targetOccurrence.timelineObject.rollTo(False)
                targetOccurrence.initialTransform = transform

            except Exception as e:
                return f"Error: Could not transform occurrence '{occurrence_name}': token ({entity_token}). Reason: {e}"


            timeline = design.timeline
            timeline.moveToEnd()

            return f"Success: Moved occurrence '{occurrence_name}' ({entity_token}) to '[{x_val}, {y_val}, {z_val}] cm')"

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()


    @ToolCollection.tool_call
    def reorient_occurrence(self, entity_token: str = "", axis: list = [0, 0, 1], target_vector: list = [1, 0, 0]) -> str:
        """
        {
          "name": "reorient_occurrence",
          "description": "Reorients the specified occurrence by rotating its local orientation so that a given axis is aligned with a specified target vector. Both the axis and target vector should be provided as arrays of three numbers representing 3D directions. The function uses Matrix3D.setToRotateTo to compute the necessary rotation transform.",
          "parameters": {
            "type": "object",
            "properties": {
              "entity_token": {
                "type": "string",
                "description": "Entity token representing an occurrence object"
              },
              "axis": {
                "type": "array",
                "description": "A list of three numbers representing the current orientation axis (direction vector) of the occurrence that will be rotated.",
                "items": { "type": "number" },
                "minItems": 3,
                "maxItems": 3
              },
              "target_vector": {
                "type": "array",
                "description": "A list of three numbers representing the target direction for the specified axis.",
                "items": { "type": "number" },
                "minItems": 3,
                "maxItems": 3
              }
            },
            "required": ["entity_token", "axis", "target_vector"],
            "returns": {
              "type": "string",
              "description": "A message indicating the result of the reorientation operation."
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

            # Validate the axis and target_vector parameters: expecting lists of 3 numbers each.
            if not (isinstance(axis, list) and len(axis) == 3):
                return "Error: 'axis' must be a list of 3 numbers."
            if not (isinstance(target_vector, list) and len(target_vector) == 3):
                return "Error: 'target_vector' must be a list of 3 numbers."

            # Create Vector3D objects from the provided lists.
            fromVector = adsk.core.Vector3D.create(axis[0], axis[1], axis[2])
            toVector = adsk.core.Vector3D.create(target_vector[0], target_vector[1], target_vector[2])

            targetOccurrence = self.get_hash_obj(entity_token)

            if not targetOccurrence:
                return f"Error: No occurrence found for entity_token '{entity_token}'"
            if not isinstance(targetOccurrence, adsk.fusion.Occurrence):
                return f"Error: '{entity_token}' does not represent an Occurrence entity"

            occurrence_name = targetOccurrence.name

            # Create a transformation matrix and set it to rotate from the 'fromVector' to the 'toVector'
            #transform = adsk.core.Matrix3D.create()
            transform = targetOccurrence.transform2
            start_translation = targetOccurrence.transform2.translation

            success = transform.setToRotateTo(fromVector, toVector)

            transform.translation = start_translation

            if not success:
                return "Error: Could not compute rotation transform using setToRotateTo."

            try:
                targetOccurrence.timelineObject.rollTo(False)
                targetOccurrence.initialTransform = transform
                #targetOccurrence.transform2 = transform
                #targetOccurrence.transform2.translation = start_translation

            except Exception as e:
                return f"Error: Could not reorient occurrence '{occurrence_name}' ({entity_token}). Reason: {e}"

            timeline = design.timeline
            timeline.moveToEnd()

            return f"Success: Reoriented occurrence '{occurrence_name}' ({entity_token}) such that the axis {axis} is rotated to align with {target_vector}."

        except Exception as e:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()









