import adsk
import adsk.core
import adsk.fusion
import adsk.cam
import pydoc

#print(dir(adsk.fusion))

#print(dir(adsk.core.Application))
#print(adsk.core.Application)


#print(dir(adsk.core.Application.get().documents))

#print(dir(adsk.fusion.DesignTypes))
#print(adsk.fusion.DesignTypes())

#print(dir(adsk.core.Application))

#print(dir(adsk.fusion))

exclude_list = []

output_list = []
def object_tree(entity, levels):


    results= {}
    count = 0
    for attr_name in dir(entity):

        # skip internal methods
        if (attr_name[0] == "_") or (attr_name in exclude_list):
            continue
        try:
            attr_val = getattr(entity, attr_name)
        except Exception as e:
            print(f"Error: attr_name: {attr_name} occurred:\n" + traceback.format_exc())
            continue

       # doc_str = help(attr_val)
#
        doc_str = pydoc.render_doc(attr_val)
        #doc_str = attr_val.__doc__
        #print(doc_str)
        output_list.append(doc_str)

        continue

        #count +=1
        #if count > 10:
        #    return

        #space = "  " * (5-levels)
        #print(f"{space}{attr_name}")

        #if any([ isinstance(attr_val, attrType) for attrType in [str, int, float, bool, tuple, list, dict]] ):
        #    results[attr_name] = attr_val

        #elif levels <= 0:
        #    results[attr_name] = str(attr_val)
        #else:
        #    results[attr_name] = object_tree(attr_val, levels-1)

    return results


object_tree(adsk.fusion, 0)
#object_tree(adsk.fusion, 0)p
#output_str = "".join(output_list)
#print(pydoc.render_doc(pydoc.writedocs))
#print(output_str)

#output_str = pydoc.render_doc(adsk.fusion)
# Render the raw documentation with potential control/backspace chars
docs_raw = pydoc.render_doc(adsk.fusion)

# Strip out formatting so repeated characters (backspaces) go away
output_str = pydoc.plain(docs_raw)
output_path = "fusion_docs.txt"


print(dir(adsk.core.geometry))

#with open(output_path, "w", encoding="utf-8") as f:
#    f.write(output_str)











