# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2019                                                    *
# *   Yorik van Havre <yorik@uncreated.net>                                 *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU Lesser General Public License (LGPL)    *
# *   as published by the Free Software Foundation; either version 2 of     *
# *   the License, or (at your option) any later version.                   *
# *   for detail see the LICENCE text file.                                 *
# *                                                                         *
# *   This program is distributed in the hope that it will be useful,       *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU Library General Public License for more details.                  *
# *                                                                         *
# *   You should have received a copy of the GNU Library General Public     *
# *   License along with this program; if not, write to the Free Software   *
# *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
# *   USA                                                                   *
# *                                                                         *
# ***************************************************************************

import json
import ifcopenshell
import math


import FreeCAD
import Draft


def getObjectsOfIfcType(objects, ifcType):
    results = []
    for object in objects:
        if hasattr(object,"IfcType"):
            if object.IfcType == ifcType:
                results.append(object)
    return results

class SIUnitCreator:
    def __init__(self, file, text, type):
        self.prefixes = ["EXA", "PETA", "TERA", "GIGA", "MEGA", "KILO", "HECTO",
            "DECA", "DECI", "CENTI", "MILLI", "MICRO", "NANO", "PICO", "FEMTO",
            "ATTO"]
        self.unitNames = ["AMPERE", "BECQUEREL", "CANDELA", "COULOMB",
            "CUBIC_METRE", "DEGREE CELSIUS", "FARAD", "GRAM", "GRAY", "HENRY",
            "HERTZ", "JOULE", "KELVIN", "LUMEN", "LUX", "MOLE", "NEWTON", "OHM",
            "PASCAL", "RADIAN", "SECOND", "SIEMENS", "SIEVERT", "SQUARE METRE",
            "METRE", "STERADIAN", "TESLA", "VOLT", "WATT", "WEBER"]
        self.text = text
        self.SIUnit = file.createIfcSIUnit(None, type, self.getSIPrefix(), self.getSIUnitName())

    def getSIPrefix(self):
        for prefix in self.prefixes:
            if prefix in self.text.upper():
                return prefix
        return None

    def getSIUnitName(self):
        for unitName in self.unitNames:
            if unitName in self.text.upper():
                return unitName
        return None

class ContextCreator:
    def __init__(self, file, objects):
        self.file = file
        self.objects = objects
        self.project_object = self.getProjectObject()
        self.project_data = self.getProjectObjectData()
        self.model_context = self.createGeometricRepresentationContext()
        self.model_view_subcontext = self.createGeometricRepresentationSubContext()
        self.target_crs = self.createTargetCRS()
        self.map_conversion = self.createMapConversion()
        self.project = self.createProject()

    def createGeometricRepresentationContext(self):
        return self.file.createIfcGeometricRepresentationContext(
            None, "Model",
            3, 1.0E-05,
            self.file.by_type("IfcAxis2Placement3D")[0],
            self.createTrueNorth())

    def createGeometricRepresentationSubContext(self):
        return self.file.createIfcGeometricRepresentationSubContext(
            "Body", "Model",
            None, None, None, None,
            self.model_context, None, "MODEL_VIEW", None)

    def createTargetCRS(self):
        try:
            SIUnit = SIUnitCreator(self.file, self.project_data["map_unit"], "LENGTHUNIT")
            return self.file.createIfcProjectedCRS(
                self.project_data["name"],
                self.project_data["description"],
                self.project_data["geodetic_datum"],
                self.project_data["vertical_datum"],
                self.project_data["map_projection"],
                self.project_data["map_zone"],
                SIUnit.SIUnit
                )
        except:
            return None

    def createMapConversion(self):
        try:
            return self.file.createIfcMapConversion(
                self.model_context, self.target_crs,
                float(self.project_data["eastings"]),
                float(self.project_data["northings"]),
                float(self.project_data["orthogonal_height"]),
                self.calculateXAxisAbscissa(),
                self.calculateXAxisOrdinate(),
                float(self.project_data["scale"])
                )
        except:
            return None

    def createTrueNorth(self):
        return self.file.createIfcDirection(
            (self.calculateXAxisAbscissa(), self.calculateXAxisOrdinate(), 0.))

    def calculateXAxisAbscissa(self):
        if "true_north" in self.project_data:
            return math.cos(math.radians(float(self.project_data["true_north"]) + 90))
        return 0.

    def calculateXAxisOrdinate(self):
        if "true_north" in self.project_data:
            return math.sin(math.radians(float(self.project_data["true_north"]) + 90))
        return 1.

    def createProject(self):
        if not self.project_object:
            return self.createAutomaticProject()
        return self.createCustomProject()

    def createAutomaticProject(self):
        return self.file.createIfcProject(
            self.getProjectGUID(),
            self.file.by_type("IfcOwnerHistory")[0],
            FreeCAD.ActiveDocument.Name, None,
            None, None, None, [self.model_context],
            self.file.by_type("IfcUnitAssignment")[0])

    def createCustomProject(self):
        return self.file.createIfcProject(
            self.getProjectGUID(),
            self.file.by_type("IfcOwnerHistory")[0],
            self.project_object.Label, self.project_object.Description,
            self.project_object.ObjectType, self.project_object.LongName,
            self.project_object.Phase,
            [self.model_context],
            self.file.by_type("IfcUnitAssignment")[0])

    def getProjectGUID(self):
        # TODO: Do not generate a new one each time, but at least this one
        # conforms to the community consensus on how a GUID is generated.
        return ifcopenshell.guid.new()

    def getProjectObject(self):
        try:
            return getObjectsOfIfcType(self.objects, "Project")[0]
        except:
            return None

    def getProjectObjectData(self):
        if not self.project_object:
            return {}
        return json.loads(self.project_object.IfcData['complex_attributes'])["RepresentationContexts"]




class recycler:

    "the compression engine - a mechanism to reuse ifc entities if needed"

    # this object has some methods identical to corresponding ifcopenshell methods,
    # but it checks if a similar entity already exists before creating a new one
    # to compress a new type, just add the necessary method here

    def __init__(self,ifcfile):

        self.ifcfile = ifcfile
        self.compress = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Arch").GetBool("ifcCompress",True)
        self.cartesianpoints = {(0,0,0):self.ifcfile[8]} # from template
        self.directions = {(1,0,0):self.ifcfile[6],(0,0,1):self.ifcfile[7],(0,1,0):self.ifcfile[10]} # from template
        self.polylines = {}
        self.polyloops = {}
        self.propertysinglevalues = {}
        self.axis2placement3ds = {'(0.0, 0.0, 0.0)(0.0, 0.0, 1.0)(1.0, 0.0, 0.0)':self.ifcfile[9]} # from template
        self.axis2placement2ds = {}
        self.localplacements = {}
        self.rgbs = {}
        self.ssrenderings = {}
        self.sstyles = {}
        self.transformationoperators = {}
        self.psas = {}
        self.spared = 0

    def createIfcCartesianPoint(self,points):
        if self.compress and points in self.cartesianpoints:
            self.spared += 1
            return self.cartesianpoints[points]
        else:
            c = self.ifcfile.createIfcCartesianPoint(points)
            if self.compress:
                self.cartesianpoints[points] = c
            return c

    def createIfcDirection(self,points):
        if self.compress and points in self.directions:
            self.spared += 1
            return self.directions[points]
        else:
            c = self.ifcfile.createIfcDirection(points)
            if self.compress:
                self.directions[points] = c
            return c

    def createIfcPolyline(self,points):
        key = "".join([str(p.Coordinates) for p in points])
        if self.compress and key in self.polylines:
            self.spared += 1
            return self.polylines[key]
        else:
            c = self.ifcfile.createIfcPolyline(points)
            if self.compress:
                self.polylines[key] = c
            return c

    def createIfcPolyLoop(self,points):
        key = "".join([str(p.Coordinates) for p in points])
        if self.compress and key in self.polyloops:
            self.spared += 1
            return self.polyloops[key]
        else:
            c = self.ifcfile.createIfcPolyLoop(points)
            if self.compress:
                self.polyloops[key] = c
            return c

    def createIfcPropertySingleValue(self,name,ptype,pvalue):
        key = str(name) + str(ptype) + str(pvalue)
        if self.compress and key in self.propertysinglevalues:
            self.spared += 1
            return self.propertysinglevalues[key]
        else:
            if isinstance(pvalue,float) and pvalue < 0.000000001: # remove the exp notation that some bim apps hate
                pvalue = 0
            c = self.ifcfile.createIfcPropertySingleValue(name,None,self.ifcfile.create_entity(ptype,pvalue),None)
            if self.compress:
                self.propertysinglevalues[key] = c
            return c

    def createIfcAxis2Placement3D(self,p1,p2,p3):
        if p2:
            tp2 = str(p2.DirectionRatios)
        else:
            tp2 = "None"
        if p3:
            tp3 = str(p3.DirectionRatios)
        else:
            tp3 = "None"
        key = str(p1.Coordinates) + tp2 + tp3
        if self.compress and key in self.axis2placement3ds:
            self.spared += 1
            return self.axis2placement3ds[key]
        else:
            c = self.ifcfile.createIfcAxis2Placement3D(p1,p2,p3)
            if self.compress:
                self.axis2placement3ds[key] = c
            return c

    def createIfcAxis2Placement2D(self,p1,p2):
        key = str(p1.Coordinates) + str(p2.DirectionRatios)
        if self.compress and key in self.axis2placement2ds:
            self.spared += 1
            return self.axis2placement2ds[key]
        else:
            c = self.ifcfile.createIfcAxis2Placement2D(p1,p2)
            if self.compress:
                self.axis2placement2ds[key] = c
            return c

    def createIfcLocalPlacement(self,gpl):
        key = str(gpl.Location.Coordinates) + str(gpl.Axis.DirectionRatios) + str(gpl.RefDirection.DirectionRatios)
        if self.compress and key in self.localplacements:
            self.spared += 1
            return self.localplacements[key]
        else:
            c = self.ifcfile.createIfcLocalPlacement(None,gpl)
            if self.compress:
                self.localplacements[key] = c
            return c

    def createIfcColourRgb(self,r,g,b):
        key = (r,g,b)
        if self.compress and key in self.rgbs:
            self.spared += 1
            return self.rgbs[key]
        else:
            c = self.ifcfile.createIfcColourRgb(None,r,g,b)
            if self.compress:
                self.rgbs[key] = c
            return c

    def createIfcSurfaceStyleRendering(self,col,trans=0):
        key = (col.Red,col.Green,col.Blue,trans)
        if self.compress and key in self.ssrenderings:
            self.spared += 1
            return self.ssrenderings[key]
        else:
            if trans == 0:
                trans = None
            c = self.ifcfile.createIfcSurfaceStyleRendering(col,trans,None,None,None,None,None,None,"FLAT")
            if self.compress:
                self.ssrenderings[key] = c
            return c

    def createIfcCartesianTransformationOperator3D(self,axis1,axis2,origin,scale,axis3):
        key = str(axis1.DirectionRatios) + str(axis2.DirectionRatios) + str(origin.Coordinates) + str(scale) + str(axis3.DirectionRatios)
        if self.compress and key in self.transformationoperators:
            self.spared += 1
            return self.transformationoperators[key]
        else:
            c = self.ifcfile.createIfcCartesianTransformationOperator3D(axis1,axis2,origin,scale,axis3)
            if self.compress:
                self.transformationoperators[key] = c
            return c

    def createIfcSurfaceStyle(self,name,r,g,b,t=0):
        if name:
            key = name + str((r,g,b))
        else:
            key = str((r,g,b))
        if self.compress and key in self.sstyles:
            self.spared += 1
            return self.sstyles[key]
        else:
            col = self.createIfcColourRgb(r,g,b)
            ssr = self.createIfcSurfaceStyleRendering(col,t)
            c = self.ifcfile.createIfcSurfaceStyle(name,"BOTH",[ssr])
            if self.compress:
                self.sstyles[key] = c
            return c

    def createIfcPresentationStyleAssignment(self,name,r,g,b,t=0):
        if name:
            key = name+str((r,g,b,t))
        else:
            key = str((r,g,b,t))
        if self.compress and key in self.psas:
            self.spared += 1
            return self.psas[key]
        else:
            iss = self.createIfcSurfaceStyle(name,r,g,b,t)
            c = self.ifcfile.createIfcPresentationStyleAssignment([iss])
            if self.compress:
                self.psas[key] = c
            return c
