import clr

clr.AddReference('ProtoGeometry')
from Autodesk.DesignScript.Geometry import *

clr.AddReference("RevitAPI")
from Autodesk.Revit.DB import *

clr.AddReference('RevitAPIUI')
from Autodesk.Revit.UI import TaskDialog

clr.AddReference("RevitServices")
from RevitServices.Persistence import DocumentManager
from RevitServices.Transactions import TransactionManager

clr.AddReference("RevitNodes")
import Revit
# Import ToProtoType, ToRevitType geometry conversion extension methods
clr.ImportExtensions(Revit.GeometryConversion)

#doc =  DocumentManager.Instance.CurrentDBDocument
msgList = []

roomsList =  UnwrapElement(IN[0])
if roomsList == None or len(roomsList) == 0:
	msgList.append("No room data found")
	roomsList = []

paramType = IN[1]
matchValues = IN[2]
if paramType == "" : paramType = None
if paramType <> None and matchValues <> None:
	if not isinstance(matchValues, list): matchValues = [matchValues]
	for i in range(len(matchValues)):
			if matchValues[i] == "N/A" : matchValues[i] = ""

matchExclusive = IN[7] #True/False exclude match or include match

groupByParamter = IN[3] #Paramter for Chart Titles
progData = []
if  groupByParamter == "" : groupByParamter = None
if groupByParamter <> None and not isinstance(groupByParamter, list):
	groupByParamter = [groupByParamter]

progData = [[] for p in groupByParamter]

roomHeightParam = IN[4]
createSolids = IN[5]
maxRoomNum = IN[6]
visParam = IN[8] #Metric to use on Chart data other than room count
creationLog = []
tryExtractSolid = True


#TransactionManager.Instance.EnsureInTransaction(doc)
paramList = []
if roomsList <> [] :
	paramList = roomsList[0].GetOrderedParameters()
	paramList =list(param.Definition.Name for param in paramList)


roomsRegions = []
roomsSolids = []
paramValues = []
visData = []
roomElements = []
roomCounter = 0
roomElem = None

def GetParameterValue(p):
	val = None
	if p.StorageType == StorageType.String: val = p.AsString()
	elif p.StorageType == StorageType.Double: val = p.AsDouble()
	elif p.StorageType == StorageType.Integer: val = p.AsInteger()
	elif p.StorageType == StorageType.ElementId: val = p.AsElementId().ToString()

	return val

def get_solid(element):
    geos = []
    for geo in element.get_Geometry(Options()):
        geos.append(geo)
    return geos[0].ToProtoType()



for i, room in enumerate(roomsList):
	if roomCounter == maxRoomNum: break
	roomCounter +=1

	paramVal = None
	if paramType <> None and paramType <> "":
		#find paramter values based on types
		for param in room.GetOrderedParameters():
		#param=room.GetParameters(paramType)[0]
			if paramType == param.Definition.Name :
				paramVal = GetParameterValue(param)

		if paramVal == "None" or paramVal == None: paramVal = ""
		paramValues.append(paramVal)

		#check filters if available
		if matchValues <> None and matchExclusive and paramVal in matchValues: continue
		if matchValues <> None and not matchExclusive and paramVal not in matchValues: continue
	#--------- Visualization Section ------------------

	#GroupBy Parameter
	if groupByParamter == None: continue
	testIndex = -1
	if len(groupByParamter) == 3 and groupByParamter[2] == "=":
		testIndex = 2
	for iP, gBParam in enumerate(groupByParamter):
		if testIndex == -1 or iP < testIndex:
			try: param = room.GetParameters(gBParam)[0]
			except:
				msg = "Parameter "+ gBParam + " not found in Room"
				if msg not in msgList: msgList.append(msg)
				continue
			progVal = GetParameterValue(param)
			if progVal == "None" or progVal == None: progVal = ""
			progData[iP].append(progVal)
		if iP == testIndex:
			test = ("EQUAL" if progData[0][-1] == progData[1][-1] else "NOT_EQUAL")
			progData[testIndex].append(test)
		#for index, val1 in enumerate(progData[0]):
			#test = 0 #; tmpVal = val1
			#test = progData[1][index] == val1
			#for i in range(1, testIndex):
				#test = progData[i][index] == tmpVal
				#if test == False: break
			#progData[testIndex].append(test)

	#Vis Data Paramter
	if visParam <> None:
		param = room.GetParameters(visParam)[0]
		visVal = GetParameterValue(param)
		if visVal == "None" or visVal == None:
			if param.StorageType == StorageType.Double : visVal = 0.0
			elif param.StorageType == StorageType.Integer : visVal = 0
			else: visVal = ""

		visData.append(visVal)


	roomElements.append(room)


	# --------Generate Room Geometry ---------------
	roomElem = room
	roomSolid = None; roomPoly = None; solidType = None

	if room.Area <= 0:
		creationLog.append("No Area")
		roomsRegions.append(roomPoly)
		roomsSolids.append(roomSolid)
		continue

	if not createSolids: continue

	solidType = "Invalid Curves"
	roomBoundaries = room.GetBoundarySegments(SpatialElementBoundaryOptions())
	roomCurves = []
	for roomBoundary in roomBoundaries:
		for boundarySegment in roomBoundary:
			curve = boundarySegment.GetCurve()
			roomCurves.append(curve.ToProtoType())
	try:
		roomPoly = PolyCurve.ByJoinedCurves(roomCurves)
		roomHeight=room.GetParameters(roomHeightParam)[0].AsDouble()
		if roomHeight == 0 or roomHeight == None: roomHeight=10
		roomSolid = roomPoly.ExtrudeAsSolid(roomHeight)
		solidType = "By Curves"
	except:
		pass

	if roomPoly == None:
		try:
			solidType = "Can't Create-Solid not tested"
			roomPoly = roomCurves
			if tryExtractSolid:
				roomSolid = get_solid(room)
				solidType = "By Solid"
		except:
			roomPoly = roomCurves
			solidType = "Can't Create"

	#if solids not created store all None values

	#store values based on success of solid creation
	roomsRegions.append(roomPoly)
	roomsSolids.append(roomSolid)
	creationLog.append(solidType)


#TransactionManager.Instance.TransactionTaskDone()

if msgList <> [] :
	msg = str(msgList)
	TaskDialog.Show('Test', str(msg))
OUT = [paramList]+[paramValues]+[roomsRegions]+[roomsSolids]+[progData]+[roomElements] + [creationLog] + [visData]
