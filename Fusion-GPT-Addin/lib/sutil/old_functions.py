
class DeleteObjects(ToolCollection):

    #@ToolCollection.tool_call
    def delete_component_sub_object(self, delete_object_array :list=[
            {"component_name": "comp1", "object_type":"jointOrigins", "object_name":"Joint Origin1"},
            {"component_name": "comp1", "object_type":"jointOrigins", "object_name":"Joint Origin1"},
            {"component_name": "comp1", "object_type":"jointOrigins", "object_name":"Joint Origin1"},
    ]) -> str:

        """
        {
            "name": "delete_component_sub_object",
            "description": "Deletes any valid object inside of component",
            "parameters": {
                "type": "object",
                "properties": {

                    "delete_object_array": {
                        "type": "array",
                        "description": "Array of objects to delete",

                        "items": {
                            "type": "object",
                            "properties": {
                                "component_name": {
                                    "type": "string",
                                    "description": "name of the component containing the object to delete"
                                },
                                "object_type": {
                                    "type": "string",
                                    "description": "type of object to delete",
                                    "enum": [ "sketches",
                                            "bRepBodies",
                                            "meshBodies",
                                            "joints",
                                            "jointOrigins",
                                            "occurrences",
                                            "rigidGroups"]
                                },
                                "object_name": {
                                    "type": "string",
                                    "description": "The name of the object to delete"
                                }
                            },
                            "required": ["component_name", "object_type", "object_name"]
                        }

                    }
                },

                "required": ["delete_object_array"],
                "returns": {
                    "type": "string",
                    "description": "A message indicating success or failure of the deletions."
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
            if not isinstance(delete_object_array, list):
                return "Error: delete_object_array must be an array/ list"

            delete_enums = [
                "sketches",
                "bRepBodies",
                "meshBodies",
                "joints",
                "jointOrigins",
                "occurrences",
                "rigidGroups",
            ]

            # add object to delete to dict, faster this way
            delete_dict = {}

            results = []
            # jonied as string and returned
            # items in array, each representing a delete task
            for delete_object in delete_object_array:
                component_name = delete_object.get("component_name")

                object_type = delete_object.get("object_type")
                object_name = delete_object.get("object_name")

                targetComponent, errors = self._find_component_by_name(component_name)

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

                # check that attr has 'itemByName' method before calling it
                if hasattr(object_class, "itemByName") == False:
                    errors = f"Error: Component {component_name}.{object_type} has no method 'itemByName'."
                    results.append(errors)
                    continue

                # select object to delete by name, sketch, body, joint, etc
                target_object = object_class.itemByName(object_name)

                # check if item by name is None
                if target_object == None:
                    errors = f"Error: Component {component_name}: {object_type} has no item {object_name}."
                    available_objects = [o.name for o in object_class]
                    errors += f" Available objects in {component_name}.{object_type}: {available_objects}"
                    results.append(errors)
                    continue

                # check if item can be delete
                if hasattr(target_object,"deleteMe") == False:
                    errors = f"Error: Component {component_name}.{object_type} object {object_name} has no attribute deleteMe."
                    results.append(errors)
                    continue


                delete_dict[f"{component_name}.{object_type}.{target_object.name}"] = target_object
                #results.append(f'Added {component_name}.{object_type} "{target_object.name}" to delete list.')


            if len(list(delete_dict.keys())) == 0:
                results.append(f"No objects to delete.")

            for k, v in delete_dict.items():
                delete_result = v.deleteMe()

                if delete_result == True:
                    results.append(f"Deleted {k}.")
                else:
                    results.append(f"Error deleting {k}.")


            #delete_name_list = []
            #deleteCollection = adsk.core.ObjectCollection.create()
            #for deleteObject in delete_list:
            #    deleteCollection.add(deleteObject)

            #design.deleteEntities(deleteCollection)
            #print(deleteCollection)

            #results.append("All object deleted")

            return "\n".join(results).strip()

        except:
            return f'Error: Failed to delete objects:\n{traceback.format_exc()}'


    #@ToolCollection.tool_call
    def delete_occurrence(self, occurrence_name: str="comp1:1") -> str:
        """
        {
            "name": "delete_occurrence",
            "description": "Deletes a occurrence from the current Fusion 360 design based on the given occurrence name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "occurrence_name": {
                        "type": "string",
                        "description": "The name of the Fusion 360 occurrence object to be deleted."
                    }
                },
                "required": ["occurrence_name"]
            }
        }
        """
        try:

            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)
            rootComp = design.rootComponent

            targetOccurrence, errors, = self._find_occurrence_by_name(occurrence_name)
            if not targetOccurrence:
                return errors

            targetOccurrence.deleteMe()

            return f'deleted {occurrence_name}'

        except Exception as e:
            return f'Error: Failed to delete occurrence "{occurrence_name}":\n{e}'








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


    def _set_entity_values(self, updates_list: list = [
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

                    entity = self.get_obj_hash(entity_token)
                if not entity:
                    result["entity_token"] = f"Error: entity_token {entity_token} not found"

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





    def set_all_timeline_groups_state(self, collapse: bool = True) -> str:
        """
        {
          "name": "set_all_timeline_groups_state",
          "description": "Expands or collapses all timeline groups in the active Fusion 360 design. The 'collapse' parameter determines whether to expand (False) or collapse (True) all timeline groups in the timeline. The function iterates through all timeline items and, for those that support the 'isExpanded' property (indicating they are groups), sets their expansion state accordingly.",
          "parameters": {
            "type": "object",
            "properties": {
              "collapse": {
                "type": "boolean",
                "description": "A boolean flag where True collapses all timeline groups and False expands them."
              }
            },
            "required": ["expand"],
            "returns": {
              "type": "string",
              "description": "A message indicating which timeline groups were modified, or an error message if the operation failed."
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
            timelineGroups = design.timeline.timelineGroups

            modified_groups = []
            # Iterate over all timeline items.
            for tlGroup in timelineGroups:

                if hasattr(tlGroup, 'isCollapsed'):
                    tlGroup.isCollapsed = collapse
                    modified_groups.append(tlGroup.name)

            if not modified_groups:
                return "No timeline groups found or none could be modified."

            state = "collapsed" if collapse else "expanded"
            return f"All timeline groups were set to {state}. Modified groups: {modified_groups}"
        except Exception as e:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()


    #@ToolCollection.tool_call
    def set_timeline_groups_state(self, group_names: list, expand: bool = True) -> str:
        """
        {
          "name": "set_timeline_groups_state",
          "description": "Expands or collapses timeline groups in the active Fusion 360 design based on the provided group names. The 'expand' parameter determines whether to expand (True) or collapse (False) the matching timeline groups. This function iterates over timeline items, identifies groups by matching their names against the provided list, and then sets their expansion state using a property or method (if available) on the timeline group objects.",
          "parameters": {
            "type": "object",
            "properties": {
              "group_names": {
                "type": "array",
                "description": "A list of strings representing the names of timeline groups to modify.",
                "items": { "type": "string" }
              },
              "expand": {
                "type": "boolean",
                "description": "A boolean flag where True expands the timeline groups and False collapses them."
              }
            },
            "required": ["group_names", "expand"],
            "returns": {
              "type": "string",
              "description": "A message indicating which timeline groups were expanded or collapsed, or an error message if the operation failed."
            }
          }
        }
        """
        try:
            # Get the Fusion 360 application and active design.
            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            design = adsk.fusion.Design.cast(product)
            timeline = design.timeline

            modified_groups = []
            # Iterate through timeline items.
            for i in range(timeline.count):
                timelineItem = timeline.item(i)
                # Check if the timeline item name is one of the target group names.
                if timelineItem.name in group_names:
                    try:
                        # Attempt to set the expansion state.
                        # Note: This assumes that timeline group items expose an 'isExpanded' property.
                        # If the API differs, adjust this section accordingly.
                        timelineItem.isExpanded = expand
                        modified_groups.append(timelineItem.name)
                    except Exception as innerEx:
                        # If an individual group cannot be modified, log and continue.
                        pass

            if not modified_groups:
                return "No matching timeline groups found or none could be modified."

            state = "expanded" if expand else "collapsed"
            return f"Timeline groups {modified_groups} were set to {state}."
        except Exception as e:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()



    #@ToolCollection.tool_call
    def set_parameter_values(self, parameter_updates: list = [["d1", 1.1], ["d2", 1.9]]) -> str:
        """
        {
          "name": "set_parameter_values",
          "description": "Sets the value of multiple parameters in the active Fusion 360 design. Each item in parameter_updates is [parameterName, newValue].",
          "parameters": {
            "type": "object",
            "properties": {
              "parameter_updates": {
                "type": "array",
                "description": "A list where each element is [parameterName, newValue]. parameterName is a string and newValue is a number.",
                "items": {
                  "type": "array",
                  "minItems": 2,
                  "maxItems": 2,
                  "items": {
                    "type": "string"
                  }
                }
              }
            },
            "required": ["parameter_updates"],
            "returns": {
              "type": "string",
              "description": "Messages indicating the result of each parameter update."
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
            results = []

            # Loop through each [parameterName, newValue] pair
            for update in parameter_updates:
                # Basic validation of each pair
                if not isinstance(update, list) or len(update) != 2:
                    results.append(f"Error: Invalid update format (expected [parameterName, newValue]): {update}")
                    continue

                parameter_name, new_value = update[0], update[1]

                # Attempt to find the parameter by name
                param = design.allParameters.itemByName(parameter_name)
                if not param:
                    results.append(f"Error: Parameter '{parameter_name}' not found.")
                    continue

                # Attempt to set the new value
                try:
                    param.value = float(new_value)
                    results.append(f"Parameter '{parameter_name}' successfully updated to {new_value}.")
                except:
                    # If direct assignment fails (e.g., read-only, locked, or expression-based),
                    # try setting the parameter expression instead
                    try:
                        if param.unit:
                            param.expression = f"{new_value} {param.unit}"
                        else:
                            param.expression = str(new_value)
                        results.append(f"Parameter '{parameter_name}' successfully updated to {new_value}.")
                    except:
                        results.append(f"Error: Failed to update parameter '{parameter_name}' to {new_value}.")

            # Combine and return all messages
            return "\n".join(results)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()






    #@ToolCollection.tool_call
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

                #object_type = entity.objectType.split(":")[-1]
                object_type = entity.__class__.__name__

                object_name = getattr(entity, "name", None)
                if object_name is None:
                    object_name = f"nameless_{object_type}_{token}"

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
                    final_val = f"Error: Failed to delete {object_type} '{object_name}' ({token}): {e}."

                results[token] = final_val

            return json.dumps(results)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()
















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




