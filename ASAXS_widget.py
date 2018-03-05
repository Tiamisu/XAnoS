from PyQt5.QtWidgets import QWidget, QApplication, QPushButton, QLabel, QLineEdit, QVBoxLayout, QMessageBox, QCheckBox, QSpinBox, QComboBox, QListWidget, QDialog, QFileDialog, QProgressBar, QTableWidget, QTableWidgetItem, QAbstractItemView, QSpinBox, QShortcut
from PyQt5.QtGui import QPalette, QKeySequence
from PyQt5.QtCore import Qt
import os
import sys
import pyqtgraph as pg
from pyqtgraph.dockarea import DockArea, Dock
from xraydb import XrayDB
from PlotWidget import PlotWidget
import copy
import numpy as np
from scipy.signal import fftconvolve, savgol_filter
from scipy.interpolate import interp1d
from scipy.optimize import minimize
from numpy.linalg import lstsq, solve
import time
from calc_cf import calc_cf
from utils import calc_prm
from readData import read1DSAXS

class ASAXS_Widget(QWidget):
    """
    This widget class is developed to perform to decouple various scattering contributions of ASAXS data. The contributions include
    1) Non resonant scattering term
    2) Cross term
    3) Resonant term
    """
    def __init__(self,parent=None):
        QWidget.__init__(self,parent)
        self.xrdb=XrayDB()
        self.cwd=os.getcwd()
        self.dataDir=copy.copy(self.cwd)
        
        self.data={}
        self.xrf_bkg={}
        self.energyLines={}
        self.ffactors={}
        self.fCounter=0
        self.minEnergy=1000000.0
        self.metaKeys=[]
        self.CF=1.0
        self.qOff=0.0
        
        self.vblayout=QVBoxLayout(self)
        self.mainDock=DockArea(self,parent)
        self.vblayout.addWidget(self.mainDock)
        
        self.dataDock=Dock('Data Dock',size=(2,8))
        self.dataPlotDock=Dock('Data Plot',size=(6,8))
        self.metaDataPlotDock=Dock('Metadata Plot',size=(6,8))
        self.edgePlotDock=Dock('Edge Plot',size=(6,8))
        self.ASAXSPlotDock=Dock('ASAXS components',size=(6,8))
        self.mainDock.addDock(self.dataDock)
        self.mainDock.addDock(self.dataPlotDock,'right')
        self.mainDock.addDock(self.metaDataPlotDock,'right')
        self.mainDock.addDock(self.edgePlotDock,'right')
        self.mainDock.addDock(self.ASAXSPlotDock,'right')
        self.mainDock.moveDock(self.edgePlotDock,'above',self.ASAXSPlotDock)
        self.mainDock.moveDock(self.metaDataPlotDock,'above',self.edgePlotDock)
        self.mainDock.moveDock(self.dataPlotDock,'above',self.metaDataPlotDock)
        
        self.create_dataDock()
        self.create_dataPlotDock()
        self.create_metaDataPlotDock()
        self.create_edgePlotDock()
        self.create_ASAXSPlotDock()
        
        self.edgeEnergy=float(self.elementEdgeComboBox.currentText().split(':')[1].lstrip())
        self.EminLineEdit.setText('%.4f'%(0.9*self.edgeEnergy))
        self.EmaxLineEdit.setText('%.4f'%(1.1*self.edgeEnergy))
        self.update_edgePlot()
        self.initialize_metaDataPlotDock()
        
        
        
    def create_dataDock(self):
        """
        This dock is to hold the information about the resonant element of interest and a list of data 
        """
        self.dataDockLayout=pg.LayoutWidget(self)
        row=0
        col=0
        dataBaseLabel=QLabel('Xray database')
        self.xrayDataBaseComboBox=QComboBox()
        self.dataDockLayout.addWidget(dataBaseLabel,row=row,col=col)
        col+=1
        self.xrayDataBaseComboBox.addItems(['NIST','Henke'])
        self.dataBase='NIST'
        self.xrayDataBaseComboBox.currentIndexChanged.connect(self.dataBaseChanged)
        self.dataDockLayout.addWidget(self.xrayDataBaseComboBox,row=row,col=col,colspan=2)
        
        row+=1
        col=0        
        elementLabel=QLabel('Resonant Element')
        self.elementComboBox=QComboBox()        
        self.elements=self.xrdb.atomic_symbols
        self.elementComboBox.addItems([str(self.xrdb.atomic_number(element))+': '+element for element in self.elements])
        self.elementComboBox.setCurrentIndex(37)
        self.dataDockLayout.addWidget(elementLabel,row=row,col=col)
        col+=1
        self.dataDockLayout.addWidget(self.elementComboBox,row=row,col=col,colspan=2)
        
        row+=1
        col=0
        elementEdge=QLabel('Energy Edge (keV)')
        self.elementEdgeComboBox=QComboBox()
        element=str(self.elementComboBox.currentText().split(': ')[1])
        edges=self.xrdb.xray_edges(element)
        self.elementEdgeComboBox.addItems([key+': %.4f'%(edges[key].edge/1000) for key in edges.keys()])
        self.dataDockLayout.addWidget(elementEdge,row=row,col=col)
        col+=1
        self.dataDockLayout.addWidget(self.elementEdgeComboBox,row=row,col=col,colspan=2)
        self.elementComboBox.currentIndexChanged.connect(self.elementChanged)
        self.elementEdgeComboBox.currentIndexChanged.connect(self.edgeChanged)
        
        row+=1
        col=0
        EOffLabel=QLabel('Energy offset (keV)')
        self.EOffLineEdit=QLineEdit('%.4f'%0.0)
        self.EOffLineEdit.returnPressed.connect(self.dataSelectionChanged)
        self.dataDockLayout.addWidget(EOffLabel,row=row,col=col)
        col+=1
        self.dataDockLayout.addWidget(self.EOffLineEdit,row=row,col=col,colspan=2)
        
        row+=1
        col=0
        delELabel=QLabel('Energy resolution (keV)')
        self.delELineEdit=QLineEdit('%.4f'%0.0)
        self.delELineEdit.returnPressed.connect(self.dataSelectionChanged)
        self.dataDockLayout.addWidget(delELabel,row=row,col=col)
        col+=1
        self.dataDockLayout.addWidget(self.delELineEdit,row=row,col=col,colspan=2)
        
        row+=1
        col=0
        linearOffsetLabel=QLabel('Linear offset')
        self.dataDockLayout.addWidget(linearOffsetLabel,row=row,col=col)
        col+=1
        self.linearOffsetLineEdit=QLineEdit('0.0')
        self.linearOffsetLineEdit.returnPressed.connect(self.dataSelectionChanged)
        self.dataDockLayout.addWidget(self.linearOffsetLineEdit,row=row,col=col,colspan=2)        
        
        row+=1
        col=0
        self.xrfBkgCheckBox=QCheckBox('XRF-Bkg Q-range (%)')
        self.xrfBkgCheckBox.setTristate(False)
        self.xrfBkgCheckBox.setEnabled(False)
        self.xrfBkgCheckBox.stateChanged.connect(self.dataSelectionChanged)
        self.xrfBkgLineEdit=QLineEdit('95:100')
        self.xrfBkgLineEdit.returnPressed.connect(self.dataSelectionChanged)
        self.xrfBkgLineEdit.setEnabled(False)
        self.dataDockLayout.addWidget(self.xrfBkgCheckBox,row=row,col=col)
        col+=1
        self.dataDockLayout.addWidget(self.xrfBkgLineEdit,row=row,col=col,colspan=2)        
        
        
        row+=1
        col=0
        dataLabel=QLabel('Data files')
        self.dataDockLayout.addWidget(dataLabel,row=row,col=col)
        self.openDataPushButton=QPushButton('Import data')
        self.openDataPushButton.clicked.connect(self.import_data)
        col+=1
        self.dataDockLayout.addWidget(self.openDataPushButton,row=row,col=col,colspan=2)
        
        
        row+=1
        col=0
        self.dataListWidget=QListWidget()
        self.dataListWidget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.dataListWidget.itemSelectionChanged.connect(self.dataSelectionChanged)
        self.dataDockLayout.addWidget(self.dataListWidget,row=row,col=col,rowspan=10,colspan=3)
        
        row+=10
        col=0
        self.removeDataPushButton=QPushButton('Remove selected Data')
        self.removeDataPushButton.clicked.connect(self.remove_data)
        self.deleteShortCut=QShortcut(QKeySequence.Delete,self)
        self.deleteShortCut.activated.connect(self.remove_data)
        self.dataDockLayout.addWidget(self.removeDataPushButton,row=row,col=col)
        col+=1
        self.saveDataPushButton=QPushButton('Save processed data')
        self.dataDockLayout.addWidget(self.saveDataPushButton,row=row,col=col,colspan=2)
        self.saveDataPushButton.clicked.connect(self.save_processed_data)
        
        row+=1
        col=0
        self.bkgScaleLineEdit=QLineEdit('1.0')
        self.dataDockLayout.addWidget(self.bkgScaleLineEdit,row=row,col=col)
        self.bkgScaleLineEdit.returnPressed.connect(self.subtract_bkg)
        col+=1
        self.bkgSubPushButton=QPushButton('Subtract Bkg')
        self.bkgSubPushButton.clicked.connect(self.subtract_bkg)
        self.bkgSubPushButton.setEnabled(False)
        self.dataDockLayout.addWidget(self.bkgSubPushButton,row=row,col=col,colspan=2)
        
        row+=1
        col=0
        self.processTypeComboBox=QComboBox()
        self.processTypeComboBox.addItems(['Mean','Sum'])
        self.processPushButton=QPushButton('Process')
        self.processPushButton.clicked.connect(self.processData)
        self.dataDockLayout.addWidget(self.processTypeComboBox,row=row,col=col)
        col+=1
        self.dataDockLayout.addWidget(self.processPushButton,row=row,col=col,colspan=2)
        
        
        row+=1
        col=0
#        self.thicknessCheckBox=QCheckBox('Sample thickness (cm)')
#        self.thicknessCheckBox.setTristate(False)
#        self.thicknessCheckBox.stateChanged.connect(self.thicknessChanged)
#        self.dataDockLayout.addWidget(self.thicknessCheckBox,row,col)
        thicknessLabel=QLabel('Sample Thickness (cm)')
        self.dataDockLayout.addWidget(thicknessLabel,row,col)
        col+=1
        self.thicknessLineEdit=QLineEdit('1.0')
        self.thicknessLineEdit.returnPressed.connect(self.thicknessChanged)
        self.dataDockLayout.addWidget(self.thicknessLineEdit,row=row,col=col,colspan=2)
        #self.thicknessLineEdit.returnPressed.connect(self.subtract_bkg)
        
        row+=1
        col=0
        standardLabel=QLabel('Standard')
        self.dataDockLayout.addWidget(standardLabel,row=row,col=col)
        col+=1
        self.standardComboBox=QComboBox()
        self.standardComboBox.addItems(['GC','Water'])
        self.dataDockLayout.addWidget(self.standardComboBox,row=row,col=col,colspan=2)
        
        row+=1
        col=0
        self.CFLineEdit=QLineEdit('1.0')
        self.CF=float(self.CFLineEdit.text())
        self.dataDockLayout.addWidget(self.CFLineEdit,row=row,col=col)
        self.CFLineEdit.returnPressed.connect(self.CF_changed)
        col+=1
        #qminqmaxLabel=QLabel('Q-range')
        self.qminqmaxLineEdit=QLineEdit('0.0:1.0')
        self.dataDockLayout.addWidget(self.qminqmaxLineEdit,row=row,col=col,colspan=2)
        self.qminqmaxLineEdit.setToolTip('Qmin:Qmax for CF calculation')
        
        
        row+=1
        col=0
        self.calcCFPushButton=QPushButton('Calculate CF')
        self.calcCFPushButton.clicked.connect(self.calc_cal_factor)
        self.dataDockLayout.addWidget(self.calcCFPushButton,row=row,col=col)
        col+=1
        self.applyCFPushButton=QPushButton('Apply CF')
        self.applyCFPushButton.clicked.connect(self.apply_calc_factor)
        self.dataDockLayout.addWidget(self.applyCFPushButton,row=row,col=col,colspan=2)
   
        
        row+=1
        col=0
        self.checkDataSpinBox=QSpinBox(self)
        self.dataDockLayout.addWidget(self.checkDataSpinBox,row=row,col=col)
        
        col+=1
        self.checkDataPushButton=QPushButton('Check Data')
        self.checkDataPushButton.clicked.connect(self.checkData)
        self.dataDockLayout.addWidget(self.checkDataPushButton,row=row,col=col)
        col+=1
        self.saveCheckDataPushButton=QPushButton('Save Data')
        self.saveCheckDataPushButton.clicked.connect(self.saveCheckData)
        self.dataDockLayout.addWidget(self.saveCheckDataPushButton,row=row,col=col)
        
        
        row+=1
        col=0
        self.ASAXSCalcTypeComboBox=QComboBox()
        self.ASAXSCalcTypeComboBox.addItems(['np.linalg.lstsq','sp.opt.minimize'])
        self.dataDockLayout.addWidget(self.ASAXSCalcTypeComboBox,row=row,col=col)
        col+=1
        self.calcASAXSPushButton=QPushButton('Calculate scattering components')
        self.calcASAXSPushButton.clicked.connect(self.ASAXS_split)
        self.dataDockLayout.addWidget(self.calcASAXSPushButton,row=row,col=col,colspan=2)
        
        row+=1
        col=0
        self.checkComponentsPushButton=QPushButton('Check component ratios')
        self.checkComponentsPushButton.clicked.connect(self.check_components)
        self.dataDockLayout.addWidget(self.checkComponentsPushButton,row=row,col=col,colspan=3)
        
        row+=1
        col=0
        self.saveASAXSPushButton=QPushButton('Save Scattering Components')
        self.saveASAXSPushButton.clicked.connect(self.save_ASAXS)
        self.saveASAXSPushButton.setEnabled(False)
        self.dataDockLayout.addWidget(self.saveASAXSPushButton,row=row,col=col,colspan=3)
        
        self.dataDock.addWidget(self.dataDockLayout)

    def calc_cal_factor(self):
        """
        Calculates the calibration factor using Intensity calibration sample. At present only Glassy carbon is used.
        """
        if len(self.dataListWidget.selectedItems())==1:
            fname=self.dataListWidget.selectedItems()[0].text().split(': ')[1]
            xmin,xmax=self.qminqmaxLineEdit.text().split(':')
#            try:
            xmin=float(xmin)
            xmax=float(xmax)
            standard=str(self.standardComboBox.currentText())
            thickness=float(self.thicknessLineEdit.text())
            energy,self.CF,self.qOff,x,y=calc_cf(fname,standard=standard,thickness=thickness,xmin=xmin,xmax=xmax)
            self.CFLineEdit.setText('%.5f,%.5f'%(self.CF,self.qOff))
            self.dataPlotWidget.add_data(x,y,yerr=None,name='std-data')
            self.apply_calc_factor()
            self.dataPlotWidget.Plot([self.dataListWidget.selectedItems()[0].text().split(': ')[0],'std-data'])
#            except:
#                QMessageBox.warning(self,'Value Error','Please provide the Qmin and QMax in qmin:qmax format and Thickness in numerical values in centimeters')
#                return
        else:
            QMessageBox.warning(self,'Selection Error','Please select a single file for calibration factor calculation.',QMessageBox.Ok)
            
    def dataBaseChanged(self):
        """
        Selects the X-ray database
        """
        self.dataBase=str(self.xrayDataBaseComboBox.currentText())
        self.elementChanged()


    def apply_calc_factor(self):
        """
        Apply the current calibration factor to all the selected data
        """
        ans=QMessageBox.question(self,'Confirm','Are you sure of applying CF to the selected data?',QMessageBox.No,QMessageBox.Yes)
        if ans==QMessageBox.Yes:
            for item in self.dataListWidget.selectedItems():
                fname=item.text().split(': ')[1]
                self.data[fname]['CF']=self.CF
                self.data[fname]['qOff']=self.qOff
            self.dataSelectionChanged()
            
        

        
    def elementChanged(self):
        """
        This function is triggered when the current index of elementComboBox changed
        """
        self.elementEdgeComboBox.currentIndexChanged.disconnect()
        self.elementEdgeComboBox.clear()
        element=str(self.elementComboBox.currentText().split(': ')[1])
        edges=self.xrdb.xray_edges(element)
        self.elementEdgeComboBox.addItems([key+': %.4f'%(edges[key].edge/1000) for key in edges.keys()])
        self.elementEdgeComboBox.setCurrentIndex(0)
        self.elementEdgeComboBox.currentIndexChanged.connect(self.edgeChanged)
        self.edgeChanged()
        
        
    def edgeChanged(self):
        """
        This function is triggerred when the current index ov edgeComboBox Changed
        """     
        self.edgeEnergy=float(self.elementEdgeComboBox.currentText().split(': ')[1])
        self.EminLineEdit.setText('%.4f'%(0.9*self.edgeEnergy))
        self.EmaxLineEdit.setText('%.4f'%(1.1*self.edgeEnergy))
        self.dataSelectionChanged()
        
        
        
    def update_edgePlot(self):
        """
        Updates the edgePlot
        """
        #try:
        emin=float(self.EminLineEdit.text())
        emax=float(self.EmaxLineEdit.text())
        esteps=int(self.EstepsLineEdit.text())
        self.edgeEnergy=float(self.elementEdgeComboBox.currentText().split(':')[1].lstrip())
        element=str(self.elementComboBox.currentText().split(': ')[1])    
        self.Evals=np.linspace(emin,emax,esteps)
        self.EOff=float(self.EOffLineEdit.text())
        self.delE=float(self.delELineEdit.text())
        self.calc_f1,self.calc_f2=self.get_f1_f2(element=element,energy=(self.Evals-self.EOff))
        #self.calc_f1=self.xrdb.f1_chantler(element=element,energy=(self.Evals-self.EOff)*1000)
        #self.calc_f2=self.xrdb.f2_chantler(element=element,energy=(self.Evals-self.EOff)*1000)
        if self.delE>=(self.Evals[1]-self.Evals[0]):
            dE=np.arange(-20.0*self.delE,20.0*self.delE,self.Evals[1]-self.Evals[0])
            kern=np.exp(-dE**2/2.0/self.delE**2)/np.sqrt(2*np.pi)/self.delE
            self.calc_f1=fftconvolve(self.calc_f1,kern,mode='same')*(self.Evals[1]-self.Evals[0])
            self.calc_f2=fftconvolve(self.calc_f2,kern,mode='same')*(self.Evals[1]-self.Evals[0])
            self.edgePlotWidget.setYLabel('Effective scattering factors')
        else:                         
            self.edgePlotWidget.setYLabel('Scattering factors')
        self.edgePlotWidget.add_data(self.Evals,self.calc_f1,name='f1')
        self.edgePlotWidget.add_data(self.Evals,self.calc_f2,name='f2')
        self.edgePlotWidget.Plot(['f1','f2'])
        self.edgePlotWidget.updatePlot()
        #except:
        #    QMessageBox.warning(self,'Value error','Please input numeric values only',QMessageBox.Ok)
        
        
        
    def import_data(self):
        """
        Imports data to populate the dataListWidget
        """
        if self.dataListWidget.count()==0:
            self.fCounter=0
        self.dataFiles=QFileDialog.getOpenFileNames(self,caption='Import data',directory=self.dataDir,filter='Data files (*.dat *.txt *.chi)')[0]
        if len(self.dataFiles)>0:
            self.dataDir=os.path.dirname(self.dataFiles[0])
            for file in self.dataFiles:
                if file not in self.data.keys():
                    item=str(self.fCounter)+': '+file
                    self.dataListWidget.addItem(item)
                    self.read_data(item)
                    self.dataListWidget.item(self.dataListWidget.count()-1).setToolTip('%.4f keV'%self.data[file]['Energy'])
                    self.fCounter+=1
                else:
                    QMessageBox.warning(self,'Import error','%s is already imported. Please remove the file to import it again'%file,QMessageBox.Ok)
            self.initialize_metaDataPlotDock()
            self.xAxisComboBox.addItems(self.metaKeys)
            self.yAxisComboBox.addItems(self.metaKeys)
            self.normAxisComboBox.addItems(self.metaKeys)
        
        
            
    def calc_XRF_baseline(self,files):
        """
        Calculates the XRF baseline for estimating XRF-backgrounds from the data 
        """
        self.minEnergy=1e7
        for file in files:
            if self.data[file]['Energy']<self.minEnergy:
                self.minEnergy=self.data[file]['Energy']
                self.xrfFile=file
        minf,maxf=self.xrfBkgLineEdit.text().split(':')
        xf_bkg_min,xf_bkg_max=float(minf)*np.max(self.data[self.xrfFile]['x'])/100.0,float(maxf)*np.max(self.data[self.xrfFile]['x'])/100.0
        try:
            self.xrf_base=np.mean(self.data[self.xrfFile]['y'][np.argwhere(self.data[self.xrfFile]['x']>xf_bkg_min)[0][0]:np.argwhere(self.data[self.xrfFile]['x']<xf_bkg_max)[-1][0]])
        except:
            self.xrf_base=0.0
        
    def read_data(self,item):
        """
        Reads the data while importing the files in the listWidget
        """
        self.smoothCheckBox.setChecked(False)
        self.mooreACSmoothingCheckBox.setChecked(False)
        num,fname=item.split(': ')
        self.data=read1DSAXS(fname,data=self.data)
        for key in self.data[fname].keys():
            if key not in self.metaKeys:
                self.metaKeys.append(key)
        self.CFLineEdit.setText('%.3f,%.5f'%(self.data[fname]['CF'],self.data[fname]['qOff']))
        self.thicknessLineEdit.setText('%.5f'%self.data[fname]['Thickness'])
        self.dataPlotWidget.add_data(self.data[fname]['x']+self.data[fname]['qOff'],self.data[fname]['CF']*self.data[fname]['y']/self.data[fname]['Thickness'],yerr=self.data[fname]['CF']*self.data[fname]['yerr']/self.data[fname]['Thickness'],name=num)
        
    def remove_data(self):
        """
        Removes selected data from the dataListWidget
        """
        ans=QMessageBox.question(self,'Confirm','Are you sure you want to remove the data from the program?',QMessageBox.No,QMessageBox.Yes)
        if ans==QMessageBox.Yes:
            self.dataListWidget.itemSelectionChanged.disconnect()
            sel_rows=[self.dataListWidget.row(item) for item in self.dataListWidget.selectedItems()]
            sel_rows.sort(reverse=True)
            for row in sel_rows:
                fname=str(self.dataListWidget.item(row).text().split(': ')[1])
                #if fname!=self.xrfFile:
                del self.data[fname]
                self.dataListWidget.takeItem(row)
            self.dataListWidget.itemSelectionChanged.connect(self.dataSelectionChanged)
        self.dataSelectionChanged()
            
    def save_processed_data(self):
        """
        Saves the data with currently processed settings
        """
        if len(self.fnames)>0:
            for fname in self.fnames:
                pfname=os.path.splitext(fname)[0]+'_proc'+os.path.splitext(fname)[1]
                header='Processed data on %s\n'%time.asctime()
                header='Original file=%s\n'%fname
                for key in self.data[fname].keys():
                    if key!='x' and key!='y' and key!='yerr' and key!='xintp' and key!='yintp' and key!='yintperr' and key!='y-flb':
                        header=header+'%s=%s\n'%(key,self.data[fname][key])
                header=header+'Q (A^-1)\tIntensity\tIntensity_error\n'
                np.savetxt(pfname,np.vstack((self.data[fname]['x'],self.data[fname]['y'],self.data[fname]['yerr'])).T,comments='#',header=header)
            QMessageBox.information(self,'Saving info','The selected processed file/s is/are saved in the same folder as the selected data.',QMessageBox.Ok)
        else:
            QMessageBox.warning(self,'Selection error','No data selected to save',QMessageBox.Ok)
        
    def CF_changed(self):
        """
        Calibration factor changed for the selected data
        """
        try:
            for fname in self.fnames:
                self.data[fname]['CF']=float(self.CFLineEdit.text())
            self.dataSelectionChanged()
        except:
            QMessageBox.warning(self,'Selection Error','Please select a data set or group of data set to change the calibraiton factor',QMessageBox.Ok)
            
    def dataSelectionChanged(self):
        """
        This triggers when the item selection changes in the dataListWidget
        """
        self.update_edgePlot()
        self.datanames=[item.text().split(': ')[0] for item in self.dataListWidget.selectedItems()]
        self.fnames=[item.text().split(': ')[1] for item in self.dataListWidget.selectedItems()]
        if self.xrfBkgCheckBox.isChecked():
            self.calc_XRF_baseline(self.fnames)
        #self.initialize_metaDataPlotDock()
        self.metaData={}
        self.metaData['x']=[]
        self.metaData['y']=[]
        self.metaData['norm']=[]
        xname=str(self.xAxisComboBox.currentText())
        yname=str(self.yAxisComboBox.currentText())
        normname=str(self.normAxisComboBox.currentText())
        for i in range(len(self.fnames)):
            fname=self.fnames[i]
            self.CFLineEdit.setText('%.3f,%.5f'%(self.data[fname]['CF'],self.data[fname]['qOff']))
            self.thicknessLineEdit.setText('%.5f'%self.data[fname]['Thickness'])
            #Collecting meta data to plot
            if xname in self.data[fname].keys() and yname in self.data[fname].keys():
                self.metaData['x'].append(self.data[fname][xname])
                self.metaData['y'].append(self.data[fname][yname])
                if normname in self.data[fname].keys():
                    self.metaData['norm'].append(self.data[fname][normname])
                else:
                    self.metaData['norm']=1.0
            #Doing the fluorescence correction
            if self.xrfBkgCheckBox.isChecked():
                if (self.edgeEnergy-self.minEnergy)>0.049:
                    minf,maxf=self.xrfBkgLineEdit.text().split(':')
                    xf_bkg_min,xf_bkg_max=float(minf)*np.max(self.data[fname]['x'])/100.0,float(maxf)*np.max(self.data[fname]['x'])/100.0
                    try:
                        self.data[fname]['xrf_bkg']=np.mean(self.data[fname]['y'][np.argwhere(self.data[fname]['x']>xf_bkg_min)[0][0]:np.argwhere(self.data[fname]['x']<xf_bkg_max)[-1][0]])-self.xrf_base
                    except:#In case no data found between the range provided
                        self.data[fname]['xrf_bkg']=0.0
                    #self.data[fname]['y-flb']=self.data[fname]['CF']*(self.data[fname]['y']-self.xrf_bkg[fname])/self.data[fname]['Thickness']
                    #self.dataPlotWidget.add_data(self.data[fname]['x'],self.data[fname]['y-flb'],yerr=self.data[fname]['CF']*self.data[fname]['yerr']/self.data[fname]['Thickness'],name=self.datanames[i])
                else:
                    QMessageBox.information(self,'XRF-background','Please collect a data atleast 50 eV below '+str(self.edgeEnergy+self.EOff)+' keV to do XRF background subtraction.')
                    return
            else:
                self.data[fname]['xrf_bkg']=0.0
            self.dataPlotWidget.add_data(self.data[fname]['x']+self.data[fname]['qOff'],self.data[fname]['CF']*(self.data[fname]['y']-self.data[fname]['xrf_bkg'])/self.data[fname]['Thickness'],yerr=self.data[fname]['CF']*self.data[fname]['yerr']/self.data[fname]['Thickness'],name=self.datanames[i])
        self.metaData['x']=np.array(self.metaData['x'])
        self.metaData['y']=np.array(self.metaData['y'])
        self.metaData['norm']=np.array(self.metaData['norm'])
        self.metaDataPlotWidget.setXLabel(self.xAxisComboBox.currentText())
        self.metaDataPlotWidget.setYLabel(self.yAxisComboBox.currentText())
        self.metaDataPlotWidget.add_data(self.metaData['x'],self.metaData['y']/self.metaData['norm'],name=self.yAxisComboBox.currentText())
        self.dataPlotWidget.Plot(self.datanames)
        element=str(self.elementComboBox.currentText().split(': ')[1])
        try:
            self.minEnergy=np.min([self.data[key]['Energy'] for key in self.data.keys()])
        except:
            self.minEnergy=0.0
        for item in self.dataListWidget.selectedItems():
            dataname, fname=item.text().split(': ')
            self.energyLines[fname]=pg.InfiniteLine(pos=self.data[fname]['Energy'],pen=self.dataPlotWidget.data[dataname].opts['pen'])
            self.edgePlotWidget.plotWidget.addItem(self.energyLines[fname])
            self.data[fname]['f1'], self.data[fname]['f2']=self.get_f1_f2(element=element,energy=self.data[fname]['Energy']-self.EOff)
            self.data[fname]['f1']=self.data[fname]['f1']*(1.0+float(self.linearOffsetLineEdit.text())*(self.data[fname]['Energy']-self.minEnergy))
            self.edgePlotWidget.plotWidget.plot([self.data[fname]['Energy']],[self.data[fname]['f1']],pen=None,symbol='o',symbolPen=self.dataPlotWidget.data[dataname].opts['pen'],symbolBrush=None)
        if len(self.datanames)>0:
            self.xrfBkgCheckBox.setEnabled(True)
            self.xrfBkgLineEdit.setEnabled(True)
        else:
            self.xrfBkgCheckBox.setCheckState(Qt.Unchecked)
            self.xrfBkgCheckBox.setEnabled(False)
            self.xrfBkgLineEdit.setEnabled(False)
        
        self.bkgSubPushButton.setDisabled(True)
        if len(self.datanames)==2:
            self.bkgSubPushButton.setEnabled(True)
        #self.raiseDock(self.dataPlotDock)
        
    def subtract_bkg(self):
        """
        Out of the two selected data subtracts one from the other to do background subtraction
        """
        if len(self.dataListWidget.selectedItems())==2:
            self.bkgScale=float(self.bkgScaleLineEdit.text())
            #self.bkgScale=self.data[self.fnames[0]]['BSDiode_corr']*self.data[self.fnames[1]]['Monitor_corr']/self.data[self.fnames[0]]['Monitor_corr']/self.data[self.fnames[1]]['BSDiode_corr']
            #self.bkgScaleLineEdit.setText('%.5f'%self.bkgScale)
            self.interpolate_data(kind='linear')
            tmp=(self.data[self.fnames[0]]['yintp']-self.bkgScale*self.data[self.fnames[1]]['yintp'])#*self.data[self.fnames[0]]['Monitor_corr']/self.data[self.fnames[0]]['BSDiode_corr']
            tmperr=np.sqrt(self.data[self.fnames[0]]['yintperr']**2+self.bkgScale**2*self.data[self.fnames[1]]['yintperr']**2)
            data=np.vstack((self.qintp,tmp,tmperr)).T
            filename=QFileDialog.getSaveFileName(self,caption='Save as',directory=os.path.dirname(self.fnames[0]),filter='Text files (*.txt)')[0]
            if filename!='':
                self.data[filename]={}
                header='Background subtracted data obtained from data1-data2 where\n data1=%s \n data2=%s\n'%(self.fnames[0],self.fnames[1])
                for key in self.data[self.fnames[0]].keys():
                    if key!='x' and key!='y' and key!='yerr' and key!='xintp' and key!='yintp' and key!='yintperr':
                        header=header+key+'='+str(self.data[self.fnames[0]][key])+'\n'
                        self.data[filename][key]=self.data[self.fnames[0]][key]
                np.savetxt(filename,data,header=header,comments='#')
                self.data[filename]['x']=self.qintp
                self.data[filename]['y']=tmp
                self.data[filename]['yerr']=tmperr
                item=str(self.fCounter)+': '+filename
                self.dataListWidget.addItem(item)
                self.dataListWidget.item(self.dataListWidget.count()-1).setToolTip(str(self.data[filename]['Energy']))
                self.dataPlotWidget.add_data(self.data[filename]['x'],self.data[filename]['y'],yerr=self.data[filename]['yerr'],name=str(self.fCounter))
                self.fCounter+=1
                self.dataListWidget.item(self.dataListWidget.count()-1).setSelected(True)
        else:
            QMessageBox.warning(self,'Data selection error','Please select only two data for background selection.',QMessageBox.Ok)
        #self.fnames.append(filename)
        #self.dataPlotWidget.Plot(self.fnames)
        
    def processData(self):
        """
        Process the selected data for calculating mean and sum
        """
        self.interpolate_data(kind='linear')
        tdata=np.zeros_like(self.data[self.fnames[0]]['yintp'])
        tdata_err=np.zeros_like(tdata)
        tlen=len(self.fnames)
        monitor=0.0
        pDiode=0.0
        diode=0.0
        pDiodeCorr=0.0
        monitorCorr=0.0
        for fname in self.fnames:
            tdata=tdata+self.data[fname]['yintp']
            tdata_err=tdata_err+self.data[fname]['yintperr']**2
            try:
                monitor=monitor+self.data[fname]['Monitor']
                pDiode=pDiode+self.data[fname]['BSDiode']
                diode=diode+self.data[fname]['Diode']
                pDiodeCorr=pDiodeCorr+self.data[fname]['BSDiode_corr']
                monitorCorr=monitorCorr+self.data[fname]['Monitor_corr']
            except:
                monitor=1.0
                pDiode=1.0
                diode=1.0
                pDiodeCorr=1.0
                monitorCorr=1.0
        if self.processTypeComboBox.currentText()=='Mean':
            tdata=tdata/tlen
            tdata_err=np.zeros_like(tdata)
            for fname in self.fnames:
                tdata_err=tdata_err+(tdata-self.data[fname]['yintp'])**2
            tdata_err=np.sqrt(tdata_err/tlen)
            monitor=monitor/tlen
            pDiode=pDiode/tlen
            diode=diode/tlen
            pDiodeCorr=pDiodeCorr/tlen
            monitorCorr=monitorCorr/tlen
        data=np.vstack((self.qintp,tdata,tdata_err)).T
        reply=QMessageBox.question(self,'Question','Do you like to save the processed data as a new file as well?',QMessageBox.Yes,QMessageBox.
                             No)
        if reply==QMessageBox.Yes:
            filename=QFileDialog.getSaveFileName(self,caption='Save as', directory=os.path.dirname(self.fnames[0]),filter='Text files (*.txt)')[0]
            if filename!='':
                self.data[filename]=copy.copy(self.data[self.fnames[0]])
                self.data[filename]['x']=self.qintp
                self.data[filename]['y']=tdata*(self.data[filename]['Thickness']+self.data[filename]['xrf_bkg'])/self.data[filename]['CF']
                self.data[filename]['yerr']=tdata_err*self.data[filename]['Thickness']/self.data[filename]['CF']
                self.data[filename]['Monitor']=monitor
                self.data[filename]['Monitor_corr']=monitorCorr
                self.data[filename]['BSDiode']=pDiode
                self.data[filename]['BSDiode_corr']=pDiodeCorr
                header='Processed data obtained by taking '+self.processTypeComboBox.currentText()+' over the following files:\n'
                for fname in self.fnames:
                    header=header+fname+'\n'
                for key in self.data[filename].keys():
                    if key!='x' and key!='y' and key!='yerr' and key!='xintp' and key!='yintp' and key!='yintperr':
                        header=header+key+'='+str(self.data[filename][key])+'\n'
                    
                np.savetxt(filename,data,header=header,comments='#')
                item=str(self.fCounter)+': '+filename
                self.dataListWidget.addItem(item)
                self.dataListWidget.item(self.dataListWidget.count()-1).setToolTip(str(self.data[filename]['Energy']))
                self.dataPlotWidget.add_data(self.data[filename]['x'],self.data[filename]['y'],yerr=self.data[filename]['yerr'],name=str(self.fCounter))
                self.fCounter+=1
                self.dataListWidget.item(self.dataListWidget.count()-1).setSelected(True)         
            
        
        
        
    def thicknessChanged(self):
        """
        Changing sample thickness of the selected data
        """
        if float(self.thicknessLineEdit.text())>1e-3:
            for item in self.dataListWidget.selectedItems():
                fname=item.text().split(': ')[1]
                self.data[fname]['Thickness']=float(self.thicknessLineEdit.text())
            self.dataSelectionChanged()
        else:
            QMessageBox.warning(self,'Value error','Please enter the thickness value above 0.001 or else you need to change the program',QMessageBox.Ok)
        
            
    
    def create_dataPlotDock(self):
        """
        This dock holds the plot of all the selected data for further analysis
        """
        self.dataPlotLayout=pg.LayoutWidget(self)
        row=0
        col=0
        self.smoothCheckBox=QCheckBox('Smoothing data')
        self.smoothCheckBox.setTristate(False)
        self.smoothCheckBox.stateChanged.connect(self.smoothData)
        self.dataPlotLayout.addWidget(self.smoothCheckBox,row=row,col=col)
        col+=1
        windowLabel=QLabel('Window size')
        self.dataPlotLayout.addWidget(windowLabel,row=row,col=col)
        col+=1
        self.windowSpinBox=QSpinBox()
        self.windowSpinBox.setMinimum(3)
        self.windowSpinBox.setMaximum(101)
        self.windowSpinBox.setSingleStep(2)
        self.windowSpinBox.valueChanged.connect(self.windowChanged)
        self.dataPlotLayout.addWidget(self.windowSpinBox,row=row,col=col)
        col+=1
        polyDegLabel=QLabel('Degree')
        self.dataPlotLayout.addWidget(polyDegLabel,row=row,col=col)
        col+=1
        self.polyDegSpinBox=QSpinBox()
        self.polyDegSpinBox.setMaximum(self.windowSpinBox.value()-1)
        self.polyDegSpinBox.setMinimum(1)
        self.polyDegSpinBox.valueChanged.connect(self.polyDegreeChanged)
        self.dataPlotLayout.addWidget(self.polyDegSpinBox,row=row,col=col)
        
        row+=1
        col=0
        self.mooreACSmoothingCheckBox=QCheckBox('Moore\'s Auto Corr. Smoothing')
        self.mooreACSmoothingCheckBox.setTristate(False)
        self.mooreACSmoothingCheckBox.stateChanged.connect(self.applyMooresAC)
        self.dataPlotLayout.addWidget(self.mooreACSmoothingCheckBox,row=row,col=col)
        col+=2
        DmaxLabel=QLabel('Dmax (Angs)')
        self.dataPlotLayout.addWidget(DmaxLabel,row=row,col=col)
        col+=1
        self.DmaxLineEdit=QLineEdit('100.0')
        self.DmaxLineEdit.returnPressed.connect(self.applyMooresAC)
        self.dataPlotLayout.addWidget(self.DmaxLineEdit,row=row,col=col)
        col+=1
        self.plotPDDFPushButton=QPushButton('Plot PDDF')
        self.plotPDDFPushButton.clicked.connect(self.plotPDDF)
        self.dataPlotLayout.addWidget(self.plotPDDFPushButton,row=row,col=col)
        
        row+=1
        col=0
        self.dataPlotWidget=PlotWidget(self)
        self.dataPlotWidget.setXLabel('Q')
        self.dataPlotWidget.setYLabel('Intensity')
        self.dataPlotLayout.addWidget(self.dataPlotWidget,row=row,col=col,colspan=5)        
        self.dataPlotDock.addWidget(self.dataPlotLayout)
        
    def create_metaDataPlotDock(self):
        """
        Creates the metaPlotDataDock
        """
        self.metaDataPlotLayout=pg.LayoutWidget(self)
        row=0
        col=0
        xAxisLabel=QLabel('X-Axis')
        self.metaDataPlotLayout.addWidget(xAxisLabel,row=row,col=col)
        col+=1
        self.xAxisComboBox=QComboBox()
        self.xAxisComboBox.currentIndexChanged.connect(self.dataSelectionChanged)
        self.metaDataPlotLayout.addWidget(self.xAxisComboBox,row=row,col=col)
        col+=2
        yAxisLabel=QLabel('Y-Axis')
        self.metaDataPlotLayout.addWidget(yAxisLabel,row=row,col=col)
        col+=1
        self.yAxisComboBox=QComboBox()
        self.yAxisComboBox.currentIndexChanged.connect(self.dataSelectionChanged)
        self.metaDataPlotLayout.addWidget(self.yAxisComboBox,row=row,col=col)
        col+=2
        normLabel=QLabel('Normalized by')
        self.metaDataPlotLayout.addWidget(normLabel,row=row,col=col)
        col+=1
        self.normAxisComboBox=QComboBox()
        self.normAxisComboBox.currentIndexChanged.connect(self.dataSelectionChanged)
        self.metaDataPlotLayout.addWidget(self.normAxisComboBox,row=row,col=col)
        
        row+=1
        col=0
        self.metaDataPlotWidget=PlotWidget(self)
        self.metaDataPlotLayout.addWidget(self.metaDataPlotWidget,row=row,col=col,colspan=8)
        self.metaDataPlotDock.addWidget(self.metaDataPlotLayout)
        
        
    def initialize_metaDataPlotDock(self):
        """
        Initialize metaDataPlotDock
        """
        self.xAxisComboBox.clear()
        self.yAxisComboBox.clear()
        self.normAxisComboBox.clear()
        self.xAxisComboBox.addItem('None')
        self.yAxisComboBox.addItem('None')
        self.normAxisComboBox.addItem('None')
        
        
        
    def applyMooresAC(self):
        """
        Apply Moore's autocorrelation function operated smoothing
        """
        if self.mooreACSmoothingCheckBox.isChecked():
            self.smoothCheckBox.setChecked(False)
            dmax=float(self.DmaxLineEdit.text())
            for fname in self.fnames:
                r,pr,q,iqc=calc_prm(self.data[fname]['x'],self.data[fname]['yraw'],self.data[fname]['yerr'],dmax=dmax)
                self.data[fname]['r']=r
                self.data[fname]['pr']=pr
                self.data[fname]['y']=iqc
                self.dataPlotWidget.add_data(self.data[fname]
                ['x'],self.data[fname]['y'],name='Moores')
                self.dataPlotWidget.Plot(self.datanames+['Moores'])
        else:
            for fname in self.fnames:
                self.data[fname]['r']=None
                self.data[fname]['pr']=None
                self.data[fname]['y']=self.data[fname]['yraw']
            self.dataSelectionChanged()
    
    def plotPDDF(self):
        """
        Plots the moore's autocorrelation function of the selected data
        """
        try:
            pg.plot(self.data[self.fnames[0]]['r'],self.data[self.fnames[0]]['pr'],pen=pg.mkPen('r',width=2))
        except:
            QMessageBox.warning(self,'Data error','Please select Moore\'s autocorrelation first',QMessageBox.Ok)
        
    def smoothData(self):
        """
        Smooth the selected data with Savitizky-Golay method
        """
        if self.smoothCheckBox.isChecked():
            self.mooreACSmoothingCheckBox.setChecked(False)
            window=self.windowSpinBox.value()
            degree=self.polyDegSpinBox.value()
            for fname in self.fnames:
                self.data[fname]['y']=savgol_filter(self.data[fname]['yraw'],window,degree,mode='nearest')
        else:
            for fname in self.fnames:
                self.data[fname]['y']=copy.copy(self.data[fname]['yraw'])
        self.dataSelectionChanged()
                
    def windowChanged(self):
        """
        Changes the window size for smoothing
        """
        self.polyDegSpinBox.setMaximum(self.windowSpinBox.value()-1)
        self.smoothData()
        
    def polyDegreeChanged(self):
        """
        Changes the degree of polynomial for smoothing
        """
        self.smoothData()
        
    def create_ASAXSPlotDock(self):
        """
        This dock holds the plots of different scattering contributions.
        """
        self.ASAXSPlotLayout=pg.LayoutWidget(self)
        row=0
        col=0
        self.ASAXSPlotWidget=PlotWidget(self)
        self.ASAXSPlotWidget.setXLabel('Q',fontsize=1)
        self.ASAXSPlotWidget.setYLabel('Intensity',fontsize=1)
        self.ASAXSPlotLayout.addWidget(self.ASAXSPlotWidget,row=row,col=col)        
        self.ASAXSPlotDock.addWidget(self.ASAXSPlotLayout)
        
        
        
    def create_edgePlotDock(self):
        """
        This dock holds the plots for scattering factors at the selected energy edge
        """
        self.edgePlotLayout=pg.LayoutWidget(self)
        row=0
        col=0
        EminLabel=QLabel('E-min (keV)')
        EmaxLabel=QLabel('E-max (keV)')
        EstepsLabel=QLabel('# of points')
        self.EminLineEdit=QLineEdit()
        self.EmaxLineEdit=QLineEdit()
        self.EstepsLineEdit=QLineEdit('1000')
        self.edgePlotLayout.addWidget(EminLabel,row=row,col=col)
        col+=1
        self.edgePlotLayout.addWidget(self.EminLineEdit,row=row,col=col)
        self.EminLineEdit.returnPressed.connect(self.dataSelectionChanged)
        col+=1        
        self.edgePlotLayout.addWidget(EmaxLabel,row=row,col=col)
        col+=1
        self.edgePlotLayout.addWidget(self.EmaxLineEdit,row=row,col=col)
        self.EmaxLineEdit.returnPressed.connect(self.dataSelectionChanged)
        col+=1
        self.edgePlotLayout.addWidget(EstepsLabel,row=row,col=col)
        col+=1
        self.edgePlotLayout.addWidget(self.EstepsLineEdit,row=row,col=col)
        self.EstepsLineEdit.returnPressed.connect(self.dataSelectionChanged)
        row+=1
        col=0
        self.edgePlotWidget=PlotWidget(self)
        self.edgePlotWidget.lineWidthLineEdit.returnPressed.connect(self.dataSelectionChanged)
        self.edgePlotWidget.pointSizeLineEdit.returnPressed.connect(self.dataSelectionChanged)
        self.edgePlotWidget.pointSizeLineEdit.setText('0')
        self.edgePlotWidget.setXLabel('Energy (keV)')
        self.edgePlotWidget.setYLabel('Scattering factors (el/Atom)')
        self.edgePlotLayout.addWidget(self.edgePlotWidget,row=row,col=col,colspan=6)        
        self.edgePlotDock.addWidget(self.edgePlotLayout)
        
        
    def interpolate_data(self,kind='linear'):
        """
        Interpolates all the selected data with the common q values
        Npt=No. of common q-values on which interpolated values will be calculated
        kind='linear','cubic'...please check the documentation of scipy.interpolate.interp1d for more options
        """
        qmin=0.0
        qmax=1e15
        
        #For getting the appropriate qmin and qmax of the interpolated data
        #for item in self.dataListWidget.selectedItems():
        for fname in self.fnames:
            #dataname, fname=item.text().split(': ')
            tmin=np.min(self.data[fname]['x']+self.data[fname]['qOff'])
            tmax=np.max(self.data[fname]['x']+self.data[fname]['qOff'])
            if tmin>qmin:
                qmin=copy.copy(tmin)
            if tmax<qmax:
                qmax=copy.copy(tmax)                
        self.qintp=np.linspace(qmin,qmax,len(self.data[fname]['x']))
        for item in self.dataListWidget.selectedItems():
            dataname, fname=item.text().split(': ')
            self.data[fname]['xintp']=self.qintp
            #if self.xrfBkgCheckBox.isChecked():
            #    fun=interp1d(self.data[fname]['x'],self.data[fname]['y-flb'],kind=kind) #Calibration factor and thickness no#rmalization are already applied
            #else:
            fun=interp1d(self.data[fname]['x']+self.qOff,self.data[fname]['CF']*(self.data[fname]['y']-self.data[fname]['xrf_bkg'])/self.data[fname]['Thickness'],kind=kind)
            funerr=interp1d(self.data[fname]['x']+self.qOff,self.data[fname]['CF']*self.data[fname]['yerr']/self.data[fname]['Thickness'],kind=kind)
            self.data[fname]['yintp']=fun(self.qintp)
            self.data[fname]['yintperr']=funerr(self.qintp)
            
    def get_f1_f2(self,element,energy):
        """
        Obtains f1 and f2 either from NIST table or Henke's function with element=element symbol and energy in keV
        """
        if self.dataBase=='NIST':
            f1=self.xrdb.f1_chantler(element=element,energy=energy*1000,smoothing=0)
            f2=self.xrdb.f2_chantler(element=element,energy=energy*1000,smoothing=0)
        else:
            f1=eval('-pdt.%s.number+pdt.%s.xray.scattering_factors(energy=energy)[0]'%(element,element))
            f2=eval('pdt.%s.xray.scattering_factors(energy=energy)[1]'%(element))
        return f1, f2
    
    def checkData(self):
        """
        Do initial check on the selected data for further ASAXS analysis
        """
        if len(self.dataListWidget.selectedItems())>0:
            self.interpolate_data()
            self.prepareData()
            dataChk=[]
            errChk=[]
            f1val=[]
            for item in self.dataListWidget.selectedItems():
                dataname, fname=item.text().split(': ')
                dataChk.append(self.data[fname]['yintp'])
                errChk.append(self.data[fname]['yintperr'])
                f1val.append(self.data[fname]['f1'])
            dataChk=np.array(dataChk)
            errChk=np.array(errChk)
            dataChk=dataChk
            errChk=errChk
            f1val=np.array(f1val)
            self.pdata=[[f1val,dataChk[:,i],errChk[:,i]] for i in range(dataChk.shape[1])]
            self.dataCheckWidget=pg.plot(self.pdata[0][0],self.pdata[0][1]/self.pdata[0][1][0],pen=None,symbol='o')
            self.checkDataSpinBox.setMinimum(0)
            self.checkDataSpinBox.setMaximum(dataChk.shape[1]-1)
            self.checkDataSpinBox.setValue(0)            
            self.checkDataLocLine=pg.InfiniteLine(pos=self.qintp[0],pen='w')
            self.dataPlotWidget.plotWidget.addItem(self.checkDataLocLine)
            self.checkDataSpinBox.valueChanged.connect(self.update_dataCheckPlot)
            self.update_dataCheckPlot()
            
    def saveCheckData(self):
        """
        Save the checked data
        """
        try:
            fname=QFileDialog.getSaveFileName(self,caption='Save checked data as',directory=self.dataDir,filter='Text files (*.txt)')[0]
            if fname !='':
                i=self.checkDataSpinBox.value()
                data=np.vstack((self.pdata[i][0],self.pdata[i][1],self.pdata[i][2])).T
                header='Data extracted at Q=%.6f'%self.qintp[i]
                np.savetxt(fname,data,header=header,comments='#')            
        except:
            QMessageBox.warning(self,'Data error','No checked data to be saved. Please click Check Data button first',QMessageBox.Ok)
        
        
    def update_dataCheckPlot(self):
        """
        Updates the dataCheckplot
        """
        i=self.checkDataSpinBox.value()
        self.dataCheckWidget.clear()
        self.dataCheckWidget.plot(self.pdata[i][0],self.pdata[i][1]/self.pdata[i][1][0],symbol='o',pen=None)
        if self.dataPlotWidget.plotWidget.getPlotItem().ctrl.logXCheck.isChecked():
            self.checkDataLocLine.setValue(np.log10(self.qintp[i]))
        else:
            self.checkDataLocLine.setValue(self.qintp[i])
        
        
    def prepareData(self):
        """
        Prepares the selected data for ASAXS splitting i.e.
        1) Interpolate the all data sets with same q values. SAXS data collection at different energies can bring different q-values
        2) Calculates the scattering factors f1 and f2 for energies at which the data were collected
        """
        self.interpolate_data()
        element=str(self.elementComboBox.currentText().split(': ')[1])
        self.AMatrix=[]
        self.BMatrix=None
        self.EOff=float(self.EOffLineEdit.text())
        #self.calc_XRF_baseline()
        self.minEnergy=np.min([self.data[key]['Energy'] for key in self.data.keys()])
        for item in self.dataListWidget.selectedItems():
            dataname, fname=item.text().split(': ')
            self.data[fname]['f1'], self.data[fname]['f2']=self.get_f1_f2(element,(self.data[fname]['Energy']-self.EOff))
            self.data[fname]['f1']=self.data[fname]['f1']*(1.0+float(self.linearOffsetLineEdit.text())*(self.data[fname]['Energy']-self.minEnergy))
            
            #self.data[fname]['f1']=self.xrdb.f1_chantler(element=element,energy=(self.data[fname]['Energy']-self.EOff)*1000)
            #self.data[fname]['f2']=self.xrdb.f2_chantler(element=element,energy=(self.data[fname]['Energy']-self.EOff)*1000)
            self.AMatrix.append([1.0, 2*self.data[fname]['f1'], self.data[fname]['f1']**2+self.data[fname]['f2']**2])
            if self.BMatrix is not None:
                self.BMatrix=np.vstack((self.BMatrix, self.data[fname]['yintp']))
            else:
                self.BMatrix=self.data[fname]['yintp']
        self.AMatrix=np.array(self.AMatrix)
        
    def ASAXS_split(self):
        #try:
        if str(self.ASAXSCalcTypeComboBox.currentText())=='np.linalg.lstsq':
            if len(self.fnames)==3:
                self.ASAXS_split_0()
            else:
                self.ASAXS_split_1()
        else:
            if len(self.fnames)==3:
                self.ASAXS_split_0()
            else:
                self.ASAXS_split_2()
        #except:
        #    QMessageBox.warning(self,'Selection error','Please select atleast three data sets to calculate the components',QMessageBox.Ok)
        
            
    def ASAXS_split_0(self):
        """
        This calculates scattering compononents out
        """
        self.prepareData()
        self.XMatrix=[]
        for i in range(len(self.qintp)):
            x=solve(self.AMatrix,self.BMatrix[:,i])
            self.XMatrix.append(x)
        self.XMatrix=np.array(self.XMatrix)
        self.ASAXSPlotWidget.add_data(self.qintp,self.XMatrix[:,0],name='SAXS-term')
        #if np.all(self.XMatrix[:,1]>0):
        self.ASAXSPlotWidget.add_data(self.qintp,self.XMatrix[:,1],name='Cross-term')
        #else:
        #    QMessageBox.warning(self,'Negative Log error','Cross terms are all negative so plotting the -ve of cross terms',QMessageBox.Ok)
        #    self.ASAXSPlotWidget.add_data(self.qintp,-self.XMatrix[:,1],name='neg Cross-term')
        self.ASAXSPlotWidget.add_data(self.qintp,self.XMatrix[:,2],name='Resonant-term')
        self.ASAXSPlotWidget.add_data(self.qintp,np.sum(np.dot([self.AMatrix[0,:]],self.XMatrix.T),axis=0),name='Total')
        self.update_ASAXSPlot()
        self.saveASAXSPushButton.setEnabled(True)
            
            
    def ASAXS_split_1(self):
        """
        This calculates scattering compononents out
        """
        if len(self.dataListWidget.selectedItems())>=3:
            self.prepareData()
            self.XMatrix=[]
            for i in range(len(self.qintp)):
                x,residuals,rank,s=lstsq(self.AMatrix,self.BMatrix[:,i])
                self.XMatrix.append(x)
            self.XMatrix=np.array(self.XMatrix)
            self.ASAXSPlotWidget.add_data(self.qintp,self.XMatrix[:,0],name='SAXS-term')
            #if np.all(self.XMatrix[:,1]>0):
            self.ASAXSPlotWidget.add_data(self.qintp,self.XMatrix[:,1],name='Cross-term')
            #else:
            #    QMessageBox.warning(self,'Negative Log error','Cross terms are all negative so plotting the -ve of cross terms',QMessageBox.Ok)
            #    self.ASAXSPlotWidget.add_data(self.qintp,-self.XMatrix[:,1],name='neg Cross-term')
            self.ASAXSPlotWidget.add_data(self.qintp,self.XMatrix[:,2],name='Resonant-term')
            self.ASAXSPlotWidget.add_data(self.qintp,np.sum(np.dot([self.AMatrix[0,:]],self.XMatrix.T),axis=0),name='Total')
            self.update_ASAXSPlot()
            self.saveASAXSPushButton.setEnabled(True)
        else:
            #self.saveASAXSPushButton.setEnabled(True)
            QMessageBox.warning(self,'Data error','Please select more than three data sets to do the calculation',QMessageBox.Ok)
            
            
    def residual(self,x,A,B):
        """
        Calculates the residual for ASAXS_split_2
        """
        return np.sum(np.array([np.sum([A[i,j]*x[j]-B[i] for j in range(3)]) for i in range(A.shape[0])])**2)
            
    def ASAXS_split_2(self):
        """
        This calculates the scattering components by constraining the SAXS and anomalous term to be positive
        """
        if len(self.fnames)>3:
            self.prepareData()
            self.XMatrix=[]
            cons=({'type': 'ineq', 'fun': lambda x: x[0]},
                   {'type': 'ineq', 'fun': lambda x: x[2]},)
            for i in range(len(self.qintp)):
                res=minimize(self.residual,[0.0,0.0,0.0],args=(self.AMatrix,self.BMatrix[:,i]),constraints=cons,bounds=((0,None),(None,None),(0,None)))
                self.XMatrix.append(res.x)
            self.XMatrix=np.array(self.XMatrix)
            self.ASAXSPlotWidget.add_data(self.qintp,self.XMatrix[:,0],name='SAXS-term')
            #if np.all(self.XMatrix[:,1]>0):
            self.ASAXSPlotWidget.add_data(self.qintp,self.XMatrix[:,1],name='Cross-term')
            #else:
            #    QMessageBox.warning(self,'Negative Log error','Cross terms are all negative so plotting the -ve of cross terms',QMessageBox.Ok)
            #    self.ASAXSPlotWidget.add_data(self.qintp,-self.XMatrix[:,1],name='neg Cross-term')
            self.ASAXSPlotWidget.add_data(self.qintp,self.XMatrix[:,2],name='Resonant-term')
            self.ASAXSPlotWidget.add_data(self.qintp,np.sum(np.dot([self.AMatrix[0,:]],self.XMatrix.T),axis=0),name='Total')
            self.update_ASAXSPlot()
            self.saveASAXSPushButton.setEnabled(True)
        else:
            #self.saveASAXSPushButton.setEnabled(True)
            QMessageBox.warning(self,'Data error','Please select more than three data sets to do the calculation',QMessageBox.Ok)
            
    def raiseDock(self,dock):
        """
        Raises the dock as the topmost
        """
        stack=dock.container().stack
        current=stack.currentWidget()
        current.label.setDim(True)
        stack.setCurrentWidget(dock)
        dock.label.setDim(False)
            
        
    def update_ASAXSPlot(self):
        """
        Updates the ASAXS plot
        """
        #datanames=[item.text().split(': ')[0] for item in self.dataListWidget.selectedItems()] 
        #if np.all(self.XMatrix[:,1]>0):
        self.ASAXSPlotWidget.Plot(['Total','SAXS-term','Cross-term','Resonant-term'])
        #else:
        #    self.ASAXSPlotWidget.Plot(['Total','SAXS-term','neg Cross-term','Resonant-term'])
        self.raiseDock(self.ASAXSPlotDock)
        #self.mainDock.moveDock(self.ASAXSPlotDock,'above',self.dataPlotDock)
        
    def check_components(self):
        """
        Checks the scattering components
        """
        try:
            pg.plot(self.qintp,self.XMatrix[:,0]*self.XMatrix[:,2]/self.XMatrix[:,1]**2,line=None,symbol='o')
        except:
            QMessageBox.warning(self,'Components not found','Please split into the components first',QMessageBox.Ok)
        
        
    def save_ASAXS(self):
        fname=QFileDialog.getSaveFileName(self,caption='Save as',directory=self.dataDir,filter='Text files (*.txt)')[0]
        if os.path.splitext(fname)[1]=='':
            fname=fname+'.txt'
        fh=open(fname,'w')
        fh.write('# Scattering components extracted on '+time.asctime()+'\n')
        fh.write('# Data files used for the the scattering components calculations are:\n')
        datafiles=[item.text().split(': ')[1] for item in self.dataListWidget.selectedItems()]
        for file in datafiles:
            fh.write('# '+file+'\n')
        fh.write('# Q \t SAXS \t Cross \t Resonant\n')
        for i in range(len(self.qintp)):
            fh.write('%.6e \t %.6e \t %.6e \t %.6e\n'%(self.qintp[i],self.XMatrix[i,0],self.XMatrix[i,1],self.XMatrix[i,2]))
        fh.close()
        
        
        
        
if __name__=='__main__':
    app=QApplication(sys.argv)
    w=ASAXS_Widget()
    w.setWindowTitle('ASAXS Widget')
    w.setGeometry(200,200,1000,800)
    
    w.show()
    sys.exit(app.exec_())
        
        
        
    
