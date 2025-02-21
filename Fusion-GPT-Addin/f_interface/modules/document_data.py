# document data
import inspect
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

    def __init__(self, ent_dict):
        super().__init__(ent_dict)



        self.SQL_PATTERN = re.compile(
            r"(?i)^\s*"
            r"(?:"

            # ----------------------------------
            # 1) SELECT statement
            # ----------------------------------
            r"SELECT\s+(?P<attributes>[\w\s,\.]+)\s+"
            r"FROM\s+(?P<objectType>\w+)"
            r"(?:\s+WHERE\s+(?P<selectWhere>"
              # Each condition: <attrName> [NOT ] (LIKE|=) ( 'someString' | number | boolean )
              # e.g. "name NOT LIKE 'gear'", "value = 10", "isLightBulbOn = true"
              r"(?:[\w\.]+\s+(?:NOT\s+)?(?:LIKE|=)\s+(?:'[^']*'|[+-]?\d+(?:\.\d+)?|true|false))"
              r"(?:\s+(?:AND|OR)\s+[\w\.]+\s+(?:NOT\s+)?(?:LIKE|=)\s+(?:'[^']*'|[+-]?\d+(?:\.\d+)?|true|false))*"
            r"))?"
            r"(?:\s+LIMIT\s+(?P<limit>\d+))?"
            r"(?:\s+OFFSET\s+(?P<offset>\d+))?"

            r"|"

            # ----------------------------------
            # 2) UPDATE statement
            # ----------------------------------
            r"UPDATE\s+(?P<updateObjectType>\w+)"
            # setClause with a lazy capture up to WHERE|LIMIT|OFFSET|end,
            # but in that clause each assignment must accept numeric or string or boolean
            r"\s+SET\s+(?P<setClause>[\w\s,=.'%\-\(\)\:\+0-9\.truefalse]+?(?=\s+(?:WHERE|LIMIT|OFFSET)|$))"
            r"(?:\s+WHERE\s+(?P<updateWhere>"
              r"(?:[\w\.]+\s+(?:NOT\s+)?(?:LIKE|=)\s+(?:'[^']*'|[+-]?\d+(?:\.\d+)?|true|false))"
              r"(?:\s+(?:AND|OR)\s+[\w\.]+\s+(?:NOT\s+)?(?:LIKE|=)\s+(?:'[^']*'|[+-]?\d+(?:\.\d+)?|true|false))*"
            r"))?"
            r"(?:\s+LIMIT\s+(?P<updateLimit>\d+))?"
            r"(?:\s+OFFSET\s+(?P<updateOffset>\d+))?"

            r")\s*$"
        )



        # Sub-pattern for each single condition in the WHERE clause, e.g.:
        self.CONDITION_PATTERN = re.compile(
            r"(?i)^\s*"
            r"([\w\.]+)\s+(?P<maybeNot>NOT\s+)?(?P<baseOp>LIKE|=)\s+"
            r"(?:'(?P<strVal>[^']*)'|(?P<numVal>[+-]?\d+(?:\.\d+)?)(?![^'])|(?P<boolVal>true|false))"
            r"\s*$"
        )

        self.ASSIGN_RE = re.compile(
            r"(?i)^\s*"
            r"([\w\.]+)\s*=\s*"    # captures the attribute name (with optional dots)
            r"(?:"
                r"'(?P<strVal>[^']*)'"                # single-quoted string
                r"|(?P<numVal>[+-]?\d+(?:\.\d+)?)"    # integer or float
                r"|(?P<boolVal>true|false)"           # boolean
            r")"
            r"\s*$"
        )



    def document_objects(self) -> dict:
        """
        {
          "name": "search_document_objects",
          "description": "SQL like query to get dats from the Fusion 360 objects in the document",
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

        design_attrs = [
            "allParameters",
            "userParameters"
            "allComponents",
        ]

        component_attrs = [ "sketches" ]
        occurrence_attrs = [ "bRepBodies" ]

        # components
        all_components = design.allComponents

        # occurrences
        all_occurrences = root_comp.allOccurrences

        all_bodies_list = []
        for occ in all_occurrences:
            all_bodies_list += occ.bRepBodies

        allBRepBodies = adsk.core.ObjectCollection.createWithArray(all_bodies_list)

        all_sketches_list = []
        all_joints_list = []
        all_joint_origins_list = []

        for comp in all_components:
            all_sketches_list += comp.sketches
            all_joints_list += comp.joints
            all_joint_origins_list += comp.jointOrigins
        allSketches = adsk.core.ObjectCollection.createWithArray(all_sketches_list)
        allJoints = adsk.core.ObjectCollection.createWithArray(all_joints_list)
        allJointOrigins = adsk.core.ObjectCollection.createWithArray(all_joint_origins_list)

        all_sketch_curves = []
        for sketch in allSketches:
            all_sketch_curves += sketch.sketchCurves
        allSketchCurves = adsk.core.ObjectCollection.createWithArray(all_sketch_curves)

        #design.userParameters
        object_dict = {
            "Parameter": design.allParameters,
            "Joint": allJoints,
            "JointOrigin": allJointOrigins,
            "Occurrence": root_comp.allOccurrences,
            "Component": all_components,
            "BRepBody": allBRepBodies,
            "Sketch":  allSketches,
            "SketchCurve": allSketchCurves
        }

        #for k,v in object_dict.items():
        #    print(f"{k}: {v.count}")

        return object_dict




    def parse_where_conditions(self, where_str: str):
        """
        Splits 'where_str' on AND/OR, returning a list of condition dicts:
        [ { 'attrName': '...', 'operator': 'NOT LIKE', 'value': 'foo', 'logicOpBefore': None|'AND'|'OR' }, ... ]
        """
        if not where_str:
            return []

        tokens = re.split(r"(?i)\s+(AND|OR)\s+", where_str.strip())
        print(tokens)
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

    def parse_set_clause(self, clause: str):
        """
        Parses something like:
            name='Housing', value=10, appearance.name='Steel', isLightBulbOn=true
        into a list of dicts:
            [
              {"attrName": "name", "value": "Housing"},
              {"attrName": "value", "value": 10},
              {"attrName": "appearance.name", "value": "Steel"},
              {"attrName": "isLightBulbOn", "value": True}
            ]
        If any assignment is unrecognized, returns {"error": "..."}.
        """
        parts = [p.strip() for p in clause.split(',')]
        out = []
        for p in parts:
            m = self.ASSIGN_RE.match(p)
            if not m:
                return {"error": f"Unrecognized assignment: {p}"}

            attr_name = m.group(1)           # e.g. "name", "appearance.name"
            str_val   = m.group("strVal")    # matched if the user wrote e.g. 'Steel'
            num_val   = m.group("numVal")    # matched if the user wrote a numeric literal
            bool_val  = m.group("boolVal")   # matched if the user wrote true/false

            # Convert the captured group to the correct Python type
            if str_val is not None:
                final_val = str_val
            elif num_val is not None:
                # interpret as float or int
                if '.' in num_val:
                    final_val = float(num_val)
                else:
                    final_val = int(num_val)
            elif bool_val is not None:
                # case-insensitive => "true", "false"
                final_val = (bool_val.lower() == "true")
            else:
                # should not happen, but just in case
                final_val = None

            out.append({"attrName": attr_name, "value": final_val})

        return out



    def parse_single_condition(self, cond_text: str):
        m = self.CONDITION_PATTERN.match(cond_text.strip())
        if not m:
            return None

        attr_name = m.group(1)
        maybe_not = m.group("maybeNot")
        base_op   = m.group("baseOp").upper()
        str_val   = m.group("strVal")
        num_val   = m.group("numVal")
        bool_val  = m.group("boolVal")
        print(bool_val)

        # If maybe_not is present => operator = "NOT <base_op>", e.g. "NOT LIKE", "NOT ="
        if maybe_not:
            operator = (maybe_not.strip() + " " + base_op).upper()
        else:
            operator = base_op

        # Determine final value
        if str_val is not None:
            # It's a string
            value = str_val
        elif num_val is not None:
            # interpret as int or float
            if '.' in num_val:
                value = float(num_val)
            else:
                value = int(num_val)
        elif bool_val is not None:
            # interpret as Python bool
            # ignoring case because of (?i) => the actual matched text might be "TRUE", "False" ...
            value = (bool_val.lower() == "true")
        else:
            value = None

        return {
            "attrName": attr_name,
            "operator": operator,
            "value": value
        }





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

            attr_val, errors = self.get_sub_attr(obj, cond["attrName"])
            val, errors = self.get_sub_attr(obj, attr_name)
            if errors:
                return errors

            if operator == "LIKE":
                return do_like_compare(attr_val, value, negate=False)
            elif operator == "NOT LIKE":
                return do_like_compare(attr_val, value, negate=True)
            elif operator == "=":
                return (attr_val == str(value))
            elif operator == "NOT =":
                return (attr_val != str(value))
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
            #print(escaped)
            escaped = escaped.replace(r'%', '.*')
            escaped = escaped.replace(r'_', '.')
            #print(escaped)

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

            if isinstance(new_val, str):
                # check if lower-cased value is in BOOL_MAP
                val_lower = new_val.lower()
                if val_lower in BOOL_MAP:
                    new_val = BOOL_MAP[val_lower]  # a Python bool
                else:
                    # fallback to the raw string if not recognized
                    new_val = new_val

            # We'll do a naive approach:
            # If 'attr_name' has a dot, e.g. "appearance.name", we handle sub-attribute
            # We'll get the sub-object except the last part, then set the last part via setattr if possible.
            parts = attr_name.split(".")

            #print()

            if len(parts) == 1:
                # direct attribute
                try:
                    setattr(obj, parts[0], new_val)
                    details[attr_name] = f"Set to {new_val}"
                    updated_something =True
                except Exception as e:
                    details[attr_name] = f"Error: {str(e)}"
            else:
                # sub-attribute
                # e.g. "appearance.name" => first get obj.appearance, then set .name
                cur_obj = obj
                for p in parts[:-1]:
                    if not hasattr(cur_obj, p):
                        details[attr_name] = "Error: sub-attribute not found."
                        break
                    cur_obj = getattr(cur_obj, p)
                    if cur_obj is None:
                        details[attr_name] = "Error: sub-attribute is None."
                        break
                else:
                    # now we set the last part
                    final_part = parts[-1]
                    try:
                        setattr(cur_obj, final_part, new_val)
                        details[attr_name] = f"Set to {new_val}"
                        updated_something = True
                    except Exception as e:
                        details[attr_name] = f"Error: {str(e)}"

        return {
            "updated": updated_something,
            "details": details
        }




    @ToolCollection.tool_call
    def run_sql_query(self, query_str: str = "SELECT name,entityToken FROM Occurrence WHERE name LIKE 'screw'") -> str:
        """
            {
              "name": "run_sql_query",
              "description": "Executes a naive, SQL-like query on the current Fusion 360 design. Supports standard SQL syntax: SELECT, UPDATE, SET, FROM, WHERE, AND, OR, LIKE, LIMIT, OFFSET, for the following object: [Occurrence, Component, BRepBody, Sketch, Joint, JointOrigin, SketchLine]. Supports . syntax to access sub attributes.Examples:\
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

            print(f"where_str {where_str}")


            limit_val = int(limit_str) if limit_str else None
            offset_val = int(offset_str) if offset_str else None

            # parse conditions in update_where_str => a list of condition dict
            conditions = self.parse_where_conditions(where_str)

            # gather objects of type update_object_type
            doc_objs = self.document_objects()
            all_objs = doc_objs.get(object_type, None)
            # validate object_type
            if all_objs is None:
                return f"Error: '{object_type}' is not a valid object type, valid objects are: {list(doc_objs.keys())} "

            # filter objects them
            filtered_objs = []
            for o in all_objs:

                match, errors = self.match_object_against_conditions(o, conditions)
                if errors != None:
                    return errors

                if match == True:
                    filtered_objs.append(o)


            # apply offset/limit
            if offset_val:
                if offset_val < len(filtered_objs):
                    filtered_objs = filtered_objs[offset_val:]
                else:
                    filtered_objs = []
            if limit_val and limit_val < len(filtered_objs):
                filtered_objs = filtered_objs[:limit_val]


            return_dict = {
                "statementType": statement_type,
                "objectType": object_type,
            }

            # If we have update_object_type => it's an UPDATE statement
            # otherwise, we treat it as SELECT
            if statement_type == "UPDATE":
                # 2) We parse the setClause into assignments: e.g. "name='Gear', appearance.name='Steel'"
                assignments = self.parse_set_clause(set_clause_str)

                if "error" in assignments:
                    return json.dumps({"error": f"Error in SET clause: {assignments['error']}"})

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
                    #"assignmentDetails": assignment_results
                })


            else:
                # SELECT statement
                # parse the attributes
                attribute_list = [a.strip() for a in attributes_str.split(",")]

                # build result
                # for each object, we gather the requested attributes
                results = []
                for obj in filtered_objs:
                    row_data = {}
                    for attr in attribute_list:
                        val, errors = self.get_sub_attr(obj, attr)
                        row_data[attr] = val

                    results.append(row_data)

                return_dict.update({
                    "count": len(results),
                    "results": results
                })


            return json.dumps(return_dict)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()


class GetStateData(ToolCollection):
    """
    methods used by Realtime API to retrive state of Fusion document
    """

    #def __init__(self):
    #    pass


    @ToolCollection.tool_call
    def describe_fusion_classes(self, class_names: list = ["Sketch"]) -> str:
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
                #print(level)

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



    def __get_recursive(self, entity, levels, total_levels):
        app = adsk.core.Application.get()
        if not app:
            return "Error: Fusion 360 is not running."

        product = app.activeProduct
        if not product or not isinstance(product, adsk.fusion.Design):
            return "Error: No active Fusion 360 design found."

        design = adsk.fusion.Design.cast(product)

        # return value
        results = {

            "methods": {},
            "objects": {},
        }

        #space = "   " * (4-levels)

        exclude_list = [
            "cast","nativeObject", "this", "thisown",
            "parent", "component",
            "parentDesign", "attributes", "baseFeatures"
        ]
        # attributes in entity
        #print()
        include_list = [
            "allComponents",
            #"components",
            "occurrence",
            "occurrences",
            "childOccurrences",
            #"component",
            "asBuiltJoints",
            "bRepBody",
            "bRepBodies",
            "sketches",
            "sketch",
            "joints",
            "joint",
            "jointOrigins",
            "constructionAxes",
            "constructionPlanes",
            "constructionPoints",

            "name",
            "entityToken",
            #"objectType",
            "sketchDimensions",
            "sketchCurves",
            "sketchTexts",
            "sketchPoints",
            "profiles",
            "bRepEdges",
            "bRepEdge",
            "faces",
            "edges",
            "edge",
            "face",
                        ]


        attrs = dir(entity)
        #attrs = ["name", "objectType"]
        for attr_name in attrs:
            if attr_name not in include_list:
                continue
            # skip internal methods
            #if (attr_name[0] == "_") or (attr_name in exclude_list):
            #    continue
            try:
                attr_val = getattr(entity, attr_name)
            except Exception as e:
                print(f"Error: attr_name: {attr_name} occurred:\n" + traceback.format_exc())
                continue

            #space = "  " * (total_levels-levels)
            #print(f"{space}{levels}:{attr_name}")

            if attr_name == "entityToken":
                results[attr_name] = self.set_obj_hash(entity)
                continue

            elif any([ isinstance(attr_val, attrType) for attrType in [str, int, float, bool]] ):
                #if attr_name not in ["name", "objectType"]:
                #    continue
                results[attr_name] = attr_val


            elif callable(attr_val) == True:
                results["methods"][attr_name] = attr_name

            # methods
            elif hasattr(attr_val, "count") == True:

                #results["iterables"][attr_name] = {"items":[]}
                #results[] = self._get_recursive(attr_val, levels-1, total_levels)

                results[attr_name] = {}
                if attr_val.count == 0:
                    continue

                results[attr_name]["items"] = []
                for item in attr_val:
                    results[attr_name]["items"].append(
                        self._get_recursive(item, levels-1, total_levels)
                    )

            elif isinstance(attr_val, object) == True:
                results["objects"][attr_name] = attr_val

            elif levels <= 0:
                results[attr_name] = str(attr_val)
            else:
                pass


        for key in ["objects", "methods"]:
            if len(results[key]) == 0:
                results.pop(key)


        return results


    #@ToolCollection.tool_call
    def __get_recursive(self, entity_token: str="", levels: int=1):

        """
        {
              "name": "get_recursive",
              "description": "Returns information about any Fusion 360 entity and its sub endities. Including components, bodies, sketches, joints, profiles, etc... Returns a JSON-encoded string describing the entire structure. This function should be called when more detailed information is needed about an entity/object or it's children",
              "parameters": {
                "type": "object",

                "properties": {
                  "entity_token_list": {
                    "type": "array",
                    "description": "A list of strings representing the entity names sub entities will be returned for",
                    "items": { "type": "string" }
                  }
                },

                "required": ["entity_token_list"],
                "returns": {
                  "type": "string",
                  "description": "A JSON-encoded string representing the structure of the current design, including name, bodies, sketches, joints, and nested occurrences for each component."
                }
              }
            }
        """

        app = adsk.core.Application.get()
        if not app:
            return "Error: Fusion 360 is not running."

        product = app.activeProduct
        if not product or not isinstance(product, adsk.fusion.Design):
            return "Error: No active Fusion 360 design found."
        # get locally stored ent
        entity = self.get_hash_obj(entity_token)

            #if entity 
        #design = adsk.fusion.Design.cast(product)
        #root_comp = design.rootComponent

        ent_data = self._get_recursive(entity, levels, total_levels=levels)

        return json.dumps(ent_data)


    # TODO probably rename
    def _get_ent_attrs(self, entity, attr_list):
        """
        get entity info, return as dict 
        """

        app = adsk.core.Application.get()
        product = app.activeProduct
        design = adsk.fusion.Design.cast(product)
        root_comp = design.rootComponent

        ent_info = { }
        # get list of attr here becaue 'hasattr' throughs error when check for entityToken
        entity_attrs = dir(entity)

        for attr in attr_list:
            target_entity = entity
            target_attr = attr

            #try:
            #    #print(f"isRef: { entity.isReferencedComponent}")
            #except Exception as e:
                #continue
                #pass
            #if isinstance(target_entity, adsk.fusion.Occurrence):

            try:
                attr_val = None

               # non direct attribute passed
                if "." in attr:
                    attr0, attr = attr.split(".")

                    try:
                        target_entity = getattr(entity, attr0, None)

                    except Exception as e:
                        print(f"Error: {attr0} target_entity {e}")
                        continue
                    if target_entity is None:
                        continue


                if attr not in entity_attrs:
                    continue


                if attr == "entityToken":
                    attr_val = self.set_obj_hash(target_entity)
                    ent_info[target_attr] = attr_val
                    continue

                attr_val = getattr(target_entity, attr, None)
                if attr_val == None:
                    continue

                elif attr == "objectType":
                    attr_val = target_entity.__class__.__name__
                elif hasattr(attr_val, "asArray") == True:
                    attr_val = attr_val.asArray()

                if not any([isinstance(attr_val, attrType) for attrType in [str, int, float, bool, tuple, list, dict]] ):
                    attr_val = str(attr_val)

                ent_info[target_attr] = attr_val

            except Exception as e:
                print(f"Error: entity: ent: {entity} _get_ent_attr An unexpected exception occurred: {e} \n" + traceback.format_exc())


        return ent_info

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

                #material_name = getattr(comp.material, "name", None)
                    #"material": material_name,

                attr_list = [
                    "entityToken",
                    "isBodiesFolderLightBulbOn",
                    "isCanvasFolderLightBulbOn",
                    "isConstructionFolderLightBulbOn",
                    "isDecalFolderLightBulbOn",
                    "isJointsFolderLightBulbOn",
                    "isOriginFolderLightBulbOn",
                    "isSketchFolderLightBulbOn",
                    "description",
                    "opacity",

                    "xConstructionAxis",
                    "yConstructionAxis",
                    "zConstructionAxis",
                    "xYConstructionPlane",
                    "xZConstructionPlane",
                    "yZConstructionPlane",
                    "material",

                    "occurrences",
                    "bRepBodies",
                    "sketches",
                    "jointOrigins",
                    "joints",
                    "constructionPlanes",
                    "constructionPoints",

                    "saveCopyAs"

                    #"modelParameters",
                ]

                # iterable attr attributes
                iter_attrs_attrs = [
                    "name",
                    "entityToken"
                ]

                comp_data = {
                    "name": comp.name,
                    "attributes": {},
                    "methods": [],
                    "objects": {},
                    "sub_entities": {}
                    #"parentDesign": comp.parentDesign.rootComponent.name
                    # Add any additional info if needed
                }

                for attr in attr_list:

                    attr_val =  getattr(comp, attr, None)

                    if attr == "entityToken":
                        attr_val = self.set_obj_hash(comp)
                        comp_data["attributes"][attr] = attr_val
                        continue

                    # primitive vals
                    elif any([isinstance(attr_val, attrType) for attrType in [str, int, float, bool]] ):
                        comp_data["attributes"][attr] = attr_val
                        continue

                    # iterable
                    elif hasattr(attr_val, "count") == True:

                        if attr_val == None:
                            continue
                        #if len(attr_val) == 0:
                        #    continue

                        sub_object_dict ={
                            "entityToken": self.set_obj_hash(attr_val, f"{comp.name}{attr}"),
                            "items": []
                        }
                        for sub_obj in attr_val:
                            ent_info = self._get_ent_attrs(sub_obj, iter_attrs_attrs)
                            sub_object_dict["items"].append(ent_info)

                        comp_data["sub_entities"][attr] = sub_object_dict
                        continue


                    elif callable(attr_val) == True:
                        comp_data["methods"].append(attr)
                        continue

                    elif attr_val != None:

                        object_dict = {
                            "entityToken": self.set_obj_hash(attr_val, f"{comp.name}{attr_val.name}"),
                            "objectType": attr_val.objectType
                        }
                        comp_data["objects"][attr] = object_dict
                        continue


                comp_list.append(comp_data)

            root_comp = design.rootComponent
            root_comp_data = {
                "name": root_comp.name,
                "id": root_comp.id,
            }

            #return json.dumps(return_data)
            return comp_list

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()


    #@ToolCollection.tool_call
    def __get_entity_entities(self, entity_token_list: str=[], sub_entity_names: str=[]) -> str:
        """
            {
              "name": "get_entity_entities",
              "description": "Returns information about any Fusion 360 entity and its sub endities. Including components, bodies, sketches, joints, profiles, etc... Returns a JSON-encoded string describing the entire structure. This function should be called when more detailed information is needed about an entity/object or it's children",
              "parameters": {
                "type": "object",

                "properties": {

                  "entity_token_list":{
                    "type": "array",
                    "description": "A list of strings representing the entity names sub entities will be returned for",
                    "items": { "type": "string" }
                  },
                  "sub_entity_names":{
                    "type": "array",
                    "description": "A list of sub entity names, to inlcude in the response, if the parameter is left empty all sub entities will be included in the response.",
                    "items": { "type": "string" }
                  }

                },

                "required": ["entity_token_list", "sub_entity_names"],
                "returns": {
                  "type": "string",
                  "description": "A JSON-encoded string representing the structure of the current design, including name, bodies, sketches, joints, and nested occurrences for each component."
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

            # return value
            results = {}

            for token in entity_token_list:

                # retrieve entity from local dict
                entity = self.get_hash_obj(token)
                if entity is None:
                    results[token] = f"Error: No entity found for entityToken {token}"
                    continue

                entity_type = entity.__class__.__name__
                entity_name = getattr(entity, "name", None)

                entityToken = None
                try:
                    if hasattr(entity, "entityToken"):
                        #attr_val =  getattr(entity, "entityToken")
                        entityToken = self.set_obj_hash(entity)
                except Exception as e:
                    print(f"Error: Failed to check entityToken attr on {entity}")

                results[token] = {
                    "name": entity_name,
                    "entityToken": entityToken,
                    "objectType": entity_type,
                    "methods":[],
                    "attributes": {},
                    "entities": {},
                }

                exclude_list = ["this", "thisown", "attributes", "documentReference", "nativeObject"]

                ent_attr_names = [
                    "name",
                    "entityToken",
                    "objectType",
                    "isDeletable",
                    "isConstruction",
                    "isLinked",
                    "isReference",
                    "isFixed",
                    "opacity",
                    "length",
                    "geometry",
                    "area",
                    "radius",
                    "origin",
                    "centroid",
                    "center",
                    "startPoint",
                    "endPoint",
                    "startVertex.geometry",
                    "endVertex.geometry",
                    "startSketchPoint.geometry",
                    "endSketchPoint.geometry",
                    "physicalProperties.centerOfMass",
                ]

                entity_results = {}
                # attributes in entity
                for attr_name in dir(entity):

                    # skip internal methods
                    if attr_name[0] == "_":
                        continue

                    if attr_name in exclude_list:
                        continue

                    # TODO somtimes getattr/hasattr fails 
                    try:
                        # calling hasattr/getattr will fail if "isReference" is False
                        if attr_name == "referencedEntity":
                            if getattr(entity, "isReference", None) != True:
                                continue

                        attr_exists = hasattr(entity, attr_name)

                    except Exception as e:
                        print(f"Error: checking hasattr {attr_name} on {entity}:\n" + traceback.format_exc())
                        continue

                    if attr_exists == False:
                        error = f"Error: {entity_type} '{entity_name}' ({token}) has not attribute {attr_name}"
                        results[token][attr_name] = error
                        continue

                    attr_dict = {}
                    try:

                        # get attribute value on the top level entity
                        attr = getattr(entity, attr_name)

                        # add only value for primitive data types
                        if any([ isinstance(attr, attrType) for attrType in [str, int, float, bool]] ):
                            attr_dict["value"] = attr

                            if attr_name == "entityToken":
                                attr = self.set_obj_hash(entity)

                            results[token]["attributes"][attr_name] = attr
                            #is_iterable = False
                            continue

                        elif callable(attr) == True:
                            if attr_name in ["cast", "classType"]:
                                continue
                            #method_data = {""}#self.describe_fusion_method(attr)
                            #results[token]["methods"].append(method_data)
                            results[token]["methods"].append(attr_name)
                            continue

                        is_iterable = True

                        if token != "design":
                            # check if iterable object array
                            if hasattr(attr, "count") == False:
                                is_iterable = False
                        else:
                            is_iterable = False

                        if isinstance(attr, str):
                            is_iterable = False

                        if is_iterable == True:
                            # filter

                            if len(sub_entity_names) != 0:

                                if attr_name not in sub_entity_names:
                                    continue

                            sketch_token_seed = f"{entityToken}{attr_name}"

                            attr_dict["entityToken"] = self.set_obj_hash(attr, sketch_token_seed)
                            attr_dict["children"] =  []

                            # iterate over entity of iterable
                            for sub_entity in attr:
                                sub_ent_attrs_dict = self._get_ent_attrs(sub_entity, ent_attr_names)
                                attr_dict["children"].append(sub_ent_attrs_dict)

                            if attr_dict["children"] == []:
                                attr_dict.pop("children")


                        else:
                            ent_attrs_dict = self._get_ent_attrs(attr, ent_attr_names)
                            attr_dict.update(ent_attrs_dict)

                        if len(attr_dict) != 0:
                            #print(f"{attr_name}: {len(attr_dict)}")
                            results[token]["entities"][attr_name] = attr_dict


                    except Exception as e:
                        return "Error: An unexpected exception occurred: {e}\n" + traceback.format_exc()


            #print(results)
            return json.dumps(results)


        except Exception as e:
            return "Error: Failed to retrieve entity information. Exception:\n" + traceback.format_exc()

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
    def __get_design_as_json(self, attributes_list=[]) -> str:
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
                "appearance.name",
                "isLightBulbOn",
                "isVisible",
                "isSuppressed",
                "isLocked",
                "isIsolated",
                "isGrounded",
                "isReferencedComponent",
                "opacity",
                "visibleOpacity",
                "transform2",
                "transform2.translation",
            ]

            if occ != None:
                #occurrence level attributes
                ent_info = self._get_ent_attrs(occ, global_attrs)
                occ_dict.update(ent_info)

                # try theese attrbutes on multiple objects
                for index, object_name in enumerate(object_types):
                    # joints that reside in the root component fail even though attr exists
                    try:
                        # body, joint, sketch etc
                        objectArray = getattr(occ, object_name)
                    except Exception as e:
                        try:
                            root_comp = design.rootComponent
                            objectArray = getattr(root_comp, object_name)
                            print(f"  {object_name} found in root comp!")
                        except Exception as e:
                            print(f"  Error 1: <{object_name}> {e}")
                            print(f" Error 2: {object_name} {e}\n{traceback.format_exc()}")
                            continue


                    object_type_dict ={
                        "entityToken": self.set_obj_hash(objectArray, occ),
                        "items": []
                    }
                    for obj in objectArray:
                        ent_info = self._get_ent_attrs(obj, global_attrs)
                        object_type_dict["items"].append(ent_info)

                    if object_type_dict["items"] == []:
                        object_type_dict.pop("items")

                    if occ_dict.get(object_name) == None:
                        occ_dict[object_name] = object_type_dict


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
           # "components": self._get_all_components(),
            "occurrences": get_component_data(None, design.rootComponent).get("occurrences", None)
        }

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
                "isCollapsed",
                "objectType",
                "entityToken",
                "entity.name",
                "entity.entityToken"

            ]


            timeline_info = []
            for t_item in timeline:

                if not t_item:
                    continue

                item_data = {}
                for attr in timeline_attr_names:

                    val, error = self.get_sub_attr(t_item, attr)
                    if val is None:
                        continue

                    if attr == "entity.entityToken":
                        val = self.set_obj_hash(t_item.entity)

                    item_data[attr] = val

                item_data["entityToken"] = self.set_obj_hash(t_item, f"timline_obj{t_item.name}")

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
                    "enityToken": self.set_obj_hash(model_param),
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

                    appearance_id = lib_appearance.id

                    # save reference to appearance object
                    appearance_hash_token = self.set_obj_hash(lib_appearance, appearance_id)

                    appearance_info = {
                        "name": lib_appearance.name,
                        "entityToken": appearance_hash_token,
                        #"id": lib_appearance.id,
                        #"appearanceType": lib_appearance.objectType,
                        #"source": library.name,

                    }

                    appearance_list.append(appearance_info)

            # Convert the collected appearance data to a JSON string
            return json.dumps(appearance_list)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()

    #@ToolCollection.tool_call
    def get_sketch_profiles(self, entity_token: str = "") -> str:
        """
        {
          "name": "get_sketch_profiles",
          "description": "Retrieves data for all sketch profiles in the sketch referenced by a token, and returns basic info about each child object in JSON format.",
          "parameters": {
            "type": "object",
            "properties": {
              "entity_token": {
                "type": "string",
                "description": "A entityToken referencing a Fusion 360 Component sketch object  (using your internal hashing system)."
              }
            },
            "required": ["entity_token"],
            "returns": {
              "type": "string",
              "description": "A JSON string describing the requested attributes and their items (if they are collections)."
            }
          }
        }
        """

        try:
            if not entity_token:
                return "Error: No entity_token provided."

            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            design = adsk.fusion.Design.cast(product)

            # Retrieve the component from your hashing system (or findEntityByToken if you prefer)
            sketch_obj = self.get_hash_obj(entity_token)
            if not sketch_obj or not isinstance(sketch_obj, adsk.fusion.Sketch):
                return f"Error: The token '{entity_token}' does not reference a Fusion Sketch."

            profile_attrs = [
                "radius",
                "length",
                "face.area",
                "face.centroid",
                "face.edges",
            ]
            results = {
                "profiles": []
            }

            for profile in sketch_obj.profiles:
                profile_dict = {
                    "entityToken": self.set_obj_hash(profile),
                    "objectType": profile.__class__.__name__
                }

                for attr in profile_attrs:
                    val, errors = self.get_sub_attr(profile, attr)
                    if val == None:
                        continue

                    elif any([ isinstance(val, attrType) for attrType in [str, int, float, bool]] ):
                        profile_dict[attr] = val

                    elif hasattr(val, "asArray"):
                        profile_dict[attr] = val.asArray()
                        continue

                results["profiles"].append(profile_dict)

            return json.dumps(results)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()

    #@ToolCollection.tool_call
    def get_sketch_curves(self, entity_token: str = "") -> str:
        """
        {
          "name": "get_sketch_curves",
          "description": "Retrieves data for all sketch curved in the  sketch referenced by a token, and returns basic info about each child object in JSON format.",
          "parameters": {
            "type": "object",
            "properties": {
              "entity_token": {
                "type": "string",
                "description": "A token referencing a Fusion 360 Sketch object  (using your internal hashing system)."
              }
            },
            "required": ["entity_token"],
            "returns": {
              "type": "string",
              "description": "A JSON string describing the requested attributes and their items (if they are collections)."
            }
          }
        }
        """

        try:
            if not entity_token:
                return "Error: No entity_token provided."
            #if not attributes_list or not isinstance(attributes_list, list):
            #    return "Error: attributes_list must be a list of attribute names."

            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            design = adsk.fusion.Design.cast(product)

            # Retrieve the component from your hashing system (or findEntityByToken if you prefer)
            sketch_obj = self.get_hash_obj(entity_token)
            if not sketch_obj or not isinstance(sketch_obj, adsk.fusion.Sketch):
                return f"Error: The token '{entity_token}' does not reference a Fusion Sketch."

            top_level_keys = ["sketchCurves"]

            results = {}

            exclude_list = []
            for attr_name in top_level_keys:

                # Check if the component has this attribute
                if not hasattr(sketch_obj, attr_name):
                    continue

                attr_value = getattr(sketch_obj, attr_name, None)
                if attr_value is None:
                    continue

                # sketch curve types
                for sub_attr in dir(attr_value):
                    sub_attr_value = getattr(attr_value, sub_attr, None)
                    if callable(sub_attr_value):
                        continue
                    elif hasattr(sub_attr_value, "count") == False:
                        continue
                    elif isinstance(sub_attr_value, str) == True:
                        continue

                    sub_attr_class = sub_attr_value.__class__.__name__
                    if sub_attr_value.count != 0:
                        results[sub_attr_class] = []

                    b_attrs = [
                        "startSketchPoint.geometry",
                        "endSketchPoint.geometry",
                        "radius",
                        "length",
                        "face.area",
                        "face.centroid"
                    ]

                    for curve in sub_attr_value:

                        curve_dict = {
                            "entityToken": self.set_obj_hash(curve),
                            "objectType": curve.__class__.__name__
                        }

                        for a in b_attrs:
                            a_val, errors = self.get_sub_attr(curve,a)
                            if a_val == None:
                                continue
                            elif any([ isinstance(a_val, attrType) for attrType in [str, int, float, bool]] ):
                                curve_dict[a] = a_val
                            elif hasattr(a_val, "asArray"):
                                curve_dict[a] = a_val.asArray()
                                continue

                        results[sub_attr_class].append(curve_dict)


            return json.dumps(results)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()

    #@ToolCollection.tool_call
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
                        #"libraryName": library.name,
                        "materials": []
                    }

                    # Enumerate materials in this library
                    for j in range(library.materials.count):
                        mat = library.materials.item(j)
                        library_info["materials"].append({
                            "name": mat.name,
                            #"id": mat.id
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




    #@ToolCollection.tool_call
    def __list_all_occurrences(self) -> str:
        """
        {
          "name": "list_all_occurrences",
          "description": "Retrieves all components in the current design and returns their basic information in a JSON array.",
          "parameters": {
            "type": "object",
            "properties": {
            },
            "required": []
          },
          "returns": {
            "type": "string",
            "description": "A JSON array of component info. Each item may include componentName and isRoot."
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

            # design.allComponents returns a collection of every component in the design
            all_occs = design.rootComponent.allOccurrences
            occ_list = []

            for occ in all_occs:
                # Basic info about each component

                token = self.set_obj_hash(occ)

                occ_data = {
                    "tame": occ.name,
                    "token": token,
                    "fullPathName": occ.fullPathName,
                }


                occ_list.append(occ_data)



            print(f"occ_list: {len(occ_list)}")
            print(f"key_list: {len(self.ent_dict.keys())}")

            return json.dumps(occ_list, indent=2)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()


    #@ToolCollection.tool_call
    def __list_all_components(self) -> str:
        """
        {
          "name": "list_all_components",
          "description": "Retrieves all components in the current design and returns their basic information in a JSON array.",
          "parameters": {
            "type": "object",
            "properties": {
            },
            "required": []
          },
          "returns": {
            "type": "string",
            "description": "A JSON array of component info. Each item may include componentName"
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

            # design.allComponents returns a collection of every component in the design
            all_comps = design.allComponents
            comp_list = []

            for comp in all_comps:
                # Basic info about each component

                token = self.set_obj_hash(comp)
                comp_data = {
                    "tame": comp.name,
                    "token": token,
                }
                comp_list.append(comp_data)

            print(f"comp_list: {len(comp_list)}")
            print(f"key_list: {len(self.ent_dict.keys())}")

            return json.dumps(comp_list, indent=2)


        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()


class SetStateData(ToolCollection):

    #@ToolCollection.tool_call
    def __set_entity_values(self,
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
                    "isFlipped",
                    "isCollapsed",
                    "isSuppressed",
                    "isBodiesFolderLightBulbOn",
                    "isCanvasFolderLightBulbOn",
                    "isConstructionFolderLightBulbOn",
                    "isDecalFolderLightBulbOn",
                    "isJointsFolderLightBulbOn",
                    "isOriginFolderLightBulbOn",
                    "isSketchFolderLightBulbOn",
                    "isFavorite",
                    "description",
                    "areProfilesShown",
                    "arePointsShown",
                    "isConstruction"
                ]
              },
              "attribute_value": {
                "type": ["boolean","number","string","null"],
                "description": "The new value to assign to the specified attribute on each entity. This can also be an EntityToken referring to another object."
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

            # if entity token passed as argument, retreive its associated object
            if isinstance(attribute_value, str) == True:
                attribute_value_obj = self.get_hash_obj(attribute_value)
                if attribute_value_obj != None:
                    attribute_value = attribute_value_obj


            for token in entity_token_list:
                if not token:
                    continue

                final_val = None

                entity = self.get_hash_obj(token)
                if not entity:
                    results[token] = f"Error: no object found for entity_token: {token}"
                    continue

                #object_type = entity.objectType.split(":")[-1]
                object_type = entity.__class__.__name__

                object_name = getattr(entity, "name", None)
                if object_name is None:
                    object_name = f"nameless_{object_type}"


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

    def describe_fusion_method(self, method) -> str:
        """
        {
          "name": "describe_fusion_method",
          "description": "Accepts a Python-callable Fusion 360 method reference and returns a JSON object describing the method's parameters and their Python types, if available. For most C++-backed Fusion 360 methods, the info will be limited.",
          "parameters": {
            "type": "object",
            "properties": {
            },
            "required": [],
            "returns": {
              "type": "string",
              "description": "A JSON object describing each parameter: { paramName, kind, default, annotation }."
            }
          }
        }
        """
        try:
            # Use the built-in inspect module to retrieve the signature
            sig = inspect.signature(method)
            param_info = []

            for name, param in sig.parameters.items():
                # param.kind can be POSITIONAL_ONLY, VAR_POSITIONAL, KEYWORD_ONLY, VAR_KEYWORD, etc.
                kind_str = str(param.kind)

                # If there's a default, we show it. If it's param.empty, there's no default
                default_val = param.default if param.default is not param.empty else None

                # For annotation, if not param.empty, we return its string.
                annotation_str = None
                if param.annotation is not param.empty:
                    annotation_str = str(param.annotation)

                param_data = {
                    "paramName": name,
                    "annotation": annotation_str
                }

                if default_val:
                    param_data["default"] = default_val

                param_info.append(param_data)

            # We can also retrieve the return annotation if present
            return_annot = None
            if sig.return_annotation is not inspect.Signature.empty:
                return_annot = str(sig.return_annotation)

            # Build a result dict
            result = {
                "methodName": getattr(method, "__name__", "unknown"),
                "parameters": param_info,
                "returnAnnotation": return_annot
            }

            return result

        except Exception as e:
            return json.dumps({
                "error": f"Could not introspect method. Reason: {str(e)}"
            })


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

                        print("{new_objects}")

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
    def set_appearance_on_entities(
        self,
        entity_token_list: list = [],
        appearance_entity_token: str = ""

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
              "appearance_entity_token": {
                "type": "string",
                "description": "entity_token for the appearance eobject."
              }
            },
            "required": ["entity_token_list", "appearance_entity_token"],
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
            if not appearance_entity_token:
                return "Error: appearance_entity_token is required."

            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            design = adsk.fusion.Design.cast(product)

            app_libraries = app.materialLibraries
            app_library = app_libraries.itemByName("Fusion Appearance Library")

            appearance = self.get_hash_obj(appearance_entity_token)

            if not appearance:
                return f"Error: No Appearance for entity token '{appearance_entity_token}'"

            app_name = appearance.name

            local_appearance = design.appearances.itemByName(app_name)
            if not local_appearance:
                # You typically need to copy the library appearance into the design before applying
                design.appearances.addByCopy(appearance, app_name)


            # We'll store messages for each token processed
            results = []


            # Process each entity token
            for token in entity_token_list:
                if not token:
                    results.append("Error: Empty token encountered.")
                    continue

                entity = self.get_hash_obj(token)
                if not entity:
                    results.append(f"Error: No entity found for token '{token}'.")
                    continue

                enttity_type = entity.__class__.__name__

                # Typically, only Occurrences have an .appearance property.
                # Some other entities (e.g., bodies) do as well, but many do not.
                if hasattr(entity, "appearance"):
                    try:
                        entity.appearance = appearance
                        results.append(f"Success: Set appearance '{app_name}' (token={appearance_entity_token}) on {enttity_type} (token={token}).")
                    except Exception as e:
                        results.append(f"Error: setting appearance on token={token}: {str(e)}")
                else:
                    results.append(f"Error: {entity_type} entity (token={token}) does not support .appearance.")

            return "\n".join(results)

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









