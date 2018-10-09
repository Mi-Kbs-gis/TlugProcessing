# -*- coding: utf-8 -*-
"""
/***************************************************************************
 TlugProcessing
                                RasterValuesToLineVertices
 TLUG Algorithms
                              -------------------
        begin                : 2018-10-05
        copyright            : (C) 2017 by Thüringer Landesanstalt für Umwelt und Geologie (TLUG)
        email                : Michael.Kuerbs@tlug.thueringen.de
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script is a processing algorithm to sample raster values to line vertices
"""

__author__ = 'Michael Kürbs'
__date__ = '2018-10-05'
__copyright__ = '(C) 2018 by Michael Kürbs by Thüringer Landesanstalt für Umwelt und Geologie (TLUG)'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

from PyQt5.QtCore import QCoreApplication
from qgis.core import (QgsProcessing,
                       QgsFeatureSink,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterVectorLayer,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterRasterLayer,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterEnum,
                       QgsProject,
                       QgsFeature,
                       QgsFeatureRequest,
                       QgsField,
                       QgsPoint,
                       QgsPointXY,
                       QgsGeometry,
                       QgsCoordinateTransform,
                       QgsProcessingException)
from .tlug_utils.TerrainModel import TerrainModel
from .tlug_utils.LaengsProfil import LaengsProfil
#from .tlug_utils.LayerSwitcher import LayerSwitcher

class AttachRasterValuesToLineVertices(QgsProcessingAlgorithm):
    """
    This is an example algorithm that takes a vector layer and
    creates a new identical one.

    It is meant to be used as an example of how to create your own
    algorithms and explain methods and variables used to do it. An
    algorithm like this will be available in all elements, and there
    is not need for additional work.

    All Processing algorithms should extend the QgsProcessingAlgorithm
    class.
    """

    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.

    OUTPUT = 'OUTPUT'
    INPUTLINELAYER = 'INPUTLINELAYER'
    INPUTRASTER = 'INPUTRASTER'
    MODUS = 'MODUS'
    
    def initAlgorithm(self, config):
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """

        # We add the input vector features source. It can have any kind of
        # geometry.
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUTLINELAYER,
                self.tr('Line Layer'),
                [QgsProcessing.TypeVectorLine]
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.INPUTRASTER,
                self.tr('Elevation Raster'),
                None, 
                False
            )
        )

        modusList = [ self.tr("only vertices"), self.tr("fill by raster resolution") ]
        self.addParameter(QgsProcessingParameterEnum(
            self.MODUS,
            self.tr('Modus'),
            options=modusList, defaultValue=0))

            # We add a feature sink in which to store our processed features (this
        # usually takes the form of a newly created vector layer when the
        # algorithm is run in QGIS).
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr('Lines with Z')
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        """
        Here is where the processing itself takes place.
        """
        rasterLayer = self.parameterAsRasterLayer(parameters, self.INPUTRASTER, context)
        vectorLayer= self.parameterAsVectorLayer(parameters, self.INPUTLINELAYER, context)
        processModus = self.parameterAsEnum(parameters, self.MODUS, context)
        features=None
        #vectorlayer must have Features
        if len(vectorLayer.selectedFeatures()) > 0:
            features=vectorLayer.selectedFeatures() #[f for f in selection]
        elif vectorLayer.featureCount() > 0:
            features=vectorLayer.getFeatures()
        else:
            msg = self.tr("Error: Line Layer "+ str(vectorLayer.name()) + " is empty!")
            feedback.reportError(msg)
            raise QgsProcessingException(msg)

        #take CRS from Rasterlayer 
        crsProject=QgsProject.instance().crs()         

        tm=TerrainModel(rasterLayer, feedback)
        
        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT,
                context, vectorLayer.fields(), vectorLayer.wkbType(), vectorLayer.crs())

        try:
            fList=[f for f in features]
            lgn=len(fList)
            if lgn > 0:
                total = 100.0 / lgn
            else:
                total=100
        except:
            msg = self.tr("no Features")
            feedback.reportError(msg)
            raise QgsProcessingException(msg)
        
        for iFeat, feature in enumerate(features):
            lineGeom = feature.geometry()
            
            geom3D=None
            if processModus==0: # nur Stützpunkte werden mit Z-Werten versehen
                points3D = tm.addZtoPoints(lineGeom.vertices(), vectorLayer.crs())
                geom3D = QgsGeometry.fromPolyline( points3D )

            
            elif processModus==1: # es werden zusätzliche Stützpunkte eingefügt in Rasterauflösung
                lp=LaengsProfil(lineGeom, tm, crsProject, feedback) # use geom in Projekt.crs
                lp.calc3DProfile()

                geom3D = lp.profilLine3d
                
                #To Do: optional wäre eine glättung sinnvoll um Stützpunkte zu reduzieren!!

            if not geom3D==None:
                #Erzeuge Feature
                newFeat = QgsFeature(feature.fields())   
                newFeat.setGeometry(geom3D)
                newFeat.setAttributes(feature.attributes())

                # Add a feature in the sink
                sink.addFeature(newFeat, QgsFeatureSink.FastInsert)
            else:
                feedback.pushInfo('Error: Feature ' + str( iFeat + 1 ) + ' Geometry can not filled with Z Values: ' + lineGeom.asWkt())
            
            # Update the progress bar
            feedback.setProgress( int( iFeat + 1 * total ) )

        msgInfo=self.tr("Lines were filled with Z - Values")
        feedback.pushInfo(msgInfo)
        # Return the results of the algorithm. In this case our only result is
        return {self.OUTPUT: dest_id}

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return self.tr( 'Attach raster values to line vertices' )

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr(self.name())

    def group(self):
        """
        Returns the name of the group this algorithm belongs to. This string
        should be localised.
        """
        return self.tr(self.groupId())

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return '3D tools'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return AttachRasterValuesToLineVertices()
