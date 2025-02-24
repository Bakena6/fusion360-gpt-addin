



const queryStrings = [
"SELECT name FROM BRepBody",

"SELECT name, appearance, area, assemblyContext, boundingBox, isLightBulbOn, isSelectable, isSheetMetal, isSolid, isTransient, orientedMinimumBoundingBox, parentComponent, vertices FROM BRepBody\n\
WHERE name LIKE '%b%' LIMIT 10",

"SELECT name,entityToken, isBodiesFolderLightBulbOn, isCanvasFolderLightBulbOn, isConstructionFolderLightBulbOn,isDecalFolderLightBulbOn,isJointsFolderLightBulbOn,isOriginFolderLightBulbOn,isSketchFolderLightBulbOn\n\
FROM Component WHERE name LIKE '%screw%' LIMIT 10",

"UPDATE Component SET isJointsFolderLightBulbOn=true, isOriginFolderLightBulbOn=true, isConstructionFolderLightBulbOn=true, isSketchFolderLightBulbOn=true, isBodiesFolderLightBulbOn=true LIMIT 10",

"UPDATE Component SET isJointsFolderLightBulbOn=false, isOriginFolderLightBulbOn=false, isConstructionFolderLightBulbOn=false, isSketchFolderLightBulbOn=false, isBodiesFolderLightBulbOn=false LIMIT 10",

"SELECT name, assemblyContext.name, appearanceSourceType, appearance.name, assemblyContext.appearance.name FROM BRepBody LIMIT 100",

"SELECT name, assemblyContext.name, appearanceSourceType, appearance.name, assemblyContext.appearance.name FROM BRepBody WHERE assemblyContext.appearance.name LIKE '%steel%' LIMIT 10",

"SELECT name, assemblyContext.name, appearanceSourceType, appearance.name, assemblyContext.appearance.name FROM BRepBody WHERE assemblyContext.appearance.name LIKE '%steel%' LIMIT 10",

"UPDATE BRepBody SET isLightBulbOn=true WHERE assemblyContext.appearance.name LIKE '%steel%' LIMIT 10",

"UPDATE BRepBody SET isLightBulbOn=true, parentComponent.isBodiesFolderLightBulbOn=true, assemblyContext.isLightBulbOn=true WHERE appearance.name LIKE '%steel%' OR assemblyContext.appearance.name LIKE '%steel%' OR assemblyContext.appearance.name LIKE '%black%'",

"UPDATE Joint SET isLightBulbOn=false WHERE jointMotion.objectType NOT LIKE '%rigid%' LIMIT 10",
"UPDATE AsBuiltJoint SET isLightBulbOn=false WHERE jointMotion.objectType NOT LIKE '%rigid%' LIMIT 10",

"UPDATE Component SET isJointsFolderLightBulbOn=true,isOriginFolderLightBulbOn=true LIMIT 20",
"SELECT name, jointMotion.objectType, isFlipped, entityToken, isLightBulbOn FROM Joint WHERE jointMotion.objectType NOT LIKE '%rigid%' LIMIT 10",

"SELECT length,endVertex,startVertex,faces,geometry\nFROM BRepEdge LIMIT 10",

"SELECT length,endVertex,startVertex,faces,geometry\nFROM BRepEdge ORDER BY length DESC LIMIT 100",

"SELECT length,body.parentComponent.name FROM BRepEdge ORDER BY length DESC LIMIT 100",

"SELECT length,objectType, boundingBox.minPoint.x, boundingBox.minPoint.y, boundingBox.minPoint.z FROM BRepEdge ORDER BY length DESC LIMIT 10",

"SELECT length,objectType, boundingBox.minPoint.x, boundingBox.minPoint.y, boundingBox.minPoint.z, boundingBox.maxPoint.x, boundingBox.maxPoint.y, boundingBox.maxPoint.z\n\
FROM BRepEdge\n\
ORDER BY boundingBox.maxPoint.z DESC LIMIT 10",

"SELECT component.name, entityToken, createdBy.name, dependentParameters, expression, role\n\
FROM Parameter",

"SELECT hasTexture,name,id\n\
FROM Appearance WHERE name LIKE '%oak%'",

"UPDATE SketchCurve SET radius = 1.1 WHERE objectType LIKE '%circle%'",

"SELECT entity.entityToken, index, errorOrWarningMessage, healthState, isRolledBack FROM TimelineObject",

"SELECT name,entityToken, assemblyContext, assemblyContext.name, assemblyContext.entityToken FROM BRepBody WHERE assemblyContext.name LIKE '%J0-Top-Plate:1%'",

"SELECT index, name, objectType,  isGroup FROM TimelineObject",

"SELECT name, physicalProperties.area, physicalProperties.volume, physicalProperties.mass, physicalProperties.centerOfMass FROM BRepBody ORDER BY physicalProperties.area DESC LIMIT 300"



];
