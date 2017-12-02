import pyqtgraph as pg
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QMessageBox, QLineEdit, QColorDialog, QCheckBox
import numpy as np

class PlotWidget(QWidget):
    """
    This class inherited from pyqtgraphs Plotwidget and adds additional compononets like:
        1) Cross-hair to view X, Y coordinates
        2) Changing plot-styles interactively
    """
    def __init__(self,parent=None):
        QWidget.__init__(self,parent)       
        self.createPlotWidget()
        self.data={}
        self.dataErrPos={}
        self.dataErrNeg={}
        self.dataErr={}
        self.data_num=0
        self.yerr={}
        
    def createPlotWidget(self):
        """
        Creates the plotWidget
        """
        self.vbLayout=QVBoxLayout(self)
        self.plotLayout=pg.LayoutWidget()
        self.vbLayout.addWidget(self.plotLayout)
        
        row=0
        col=0
        lineWidthLabel=QLabel('Line width')
        self.lineWidthLineEdit=QLineEdit('2')
        self.lineWidthLineEdit.returnPressed.connect(self.updatePlot)
        pointSizeLabel=QLabel('Point size')
        self.pointSizeLineEdit=QLineEdit('5')
        self.pointSizeLineEdit.returnPressed.connect(self.updatePlot)
        self.errorbarCheckBox=QCheckBox('Errorbar')
        self.errorbarCheckBox.stateChanged.connect(self.errorbarChanged)
        self.plotLayout.addWidget(lineWidthLabel,row=row,col=col)
        col+=1
        self.plotLayout.addWidget(self.lineWidthLineEdit,row=row,col=col)
        col+=1
        self.plotLayout.addWidget(pointSizeLabel,row=row,col=col)
        col+=1
        self.plotLayout.addWidget(self.pointSizeLineEdit,row=row,col=col)
        col+=1
        self.plotLayout.addWidget(self.errorbarCheckBox,row=row,col=col)
        col=0
        row+=1
        self.plotWidget=pg.PlotWidget(background='k')
        self.plotWidget.getPlotItem().vb.scene().sigMouseMoved.connect(self.mouseMoved)
        self.legendItem=pg.LegendItem(offset=(0.0,1.0))
        self.legendItem.setParentItem(self.plotWidget.getPlotItem())
        self.plotLayout.addWidget(self.plotWidget,row=row,col=col,colspan=5)                                  
        self.crosshairLabel=QLabel(u'X=%+0.5f , y=%+0.5f'%(0.0,0.0))
        row+=1
        col=0
        self.plotLayout.addWidget(self.crosshairLabel,row=row,col=col)
        
        
        
    def mouseMoved(self,pos):
        pointer=self.plotWidget.getPlotItem().vb.mapSceneToView(pos)
        x,y=pointer.x(),pointer.y()
        if self.plotWidget.getPlotItem().ctrl.logXCheck.isChecked():
            x=10**x
        if self.plotWidget.getPlotItem().ctrl.logYCheck.isChecked():
            y=10**y
        self.crosshairLabel.setText(u'X=%+0.5f, Y=%+0.5e'%(x,y))
        
        
    def add_data(self,x,y,yerr=None,name=None):
        """
        Adds data into the plot where:
            x=Array of x-values
            y=Array of y-values
            yerr=Array of yerr-values. If None yerr will be set to sqrt(y)
            name=any string to be used for the key to put the data
        """
        if yerr is None:
            yerr=np.ones_like(y)
        if len(x)==len(y) and len(y)==len(yerr):
            if name is None:
                dname=str(self.data_num)
            else:
                dname=name
            if np.all(yerr==1):
                self.yerr[dname]=False
            else:
                self.yerr[dname]=True
            if dname in self.data.keys():
                color=self.data[dname].opts['pen'].color()
                self.data[dname].setData(x,y,pen=pg.mkPen(color=color,width=float(self.lineWidthLineEdit.text())),symbol='o',symbolSize=float(self.pointSizeLineEdit.text()),symbolPen=pg.mkPen(color=color),symbolBrush=pg.mkBrush(color=color))
                #self.data[dname].setPen(pg.mkPen(color=pg.intColor(np.random.choice(range(0,210),1)[0]),width=int(self.lineWidthLineEdit.text())))
                #if self.errorbarCheckBox.isChecked():
                self.dataErrPos[dname].setData(x,y+yerr)
                self.dataErrNeg[dname].setData(x,y-yerr)
                self.dataErr[dname].setCurves(self.dataErrPos[dname],self.dataErrNeg[dname])
            else: 
                color=pg.intColor(np.random.choice(range(0,210),1)[0])
                self.data[dname]=pg.PlotDataItem(x,y,pen=pg.mkPen(color=color,width=float(self.lineWidthLineEdit.text())),symbol='o',symbolSize=float(self.pointSizeLineEdit.text()),symbolPen=pg.mkPen(color=color),symbolBrush=pg.mkBrush(color=color))
                
                self.data[dname].curve.setClickable(True,width=10)
                self.data[dname].sigClicked.connect(self.colorChanged)
                #if self.errorbarCheckBox.isChecked():
                self.dataErrPos[dname]=pg.PlotDataItem(x,y+yerr)
                self.dataErrNeg[dname]=pg.PlotDataItem(x,y-yerr)
                self.dataErr[dname]=pg.FillBetweenItem(curve1=self.dataErrPos[dname],curve2=self.dataErrNeg[dname],brush=pg.mkBrush(color=pg.hsvColor(1.0,sat=0.0,alpha=0.2)))
                self.data_num+=1
                #if len(x)>1:
                self.Plot([dname])
        else:
            QMessageBox.warning(self,'Data error','The dimensions of x, y or yerr are not matching',QMessageBox.Ok)
            
    def colorChanged(self,item):
        """
        Color of the item changed
        """
        color=QColorDialog.getColor()
        item.setPen(pg.mkPen(color=color,width=int(self.lineWidthLineEdit.text())))
        item.setSymbolBrush(pg.mkBrush(color=color))
        item.setSymbolPen(pg.mkPen(color=color))
    
    def errorbarChanged(self):
        """
        Updates the plot checking the Errorbar is checked or not
        """
        self.Plot(self.selDataNames)
            
        
    def Plot(self,datanames):
        """
        Plots all the data in the memory with errorbars where:
            datanames is the list of datanames
        """
        self.selDataNames=datanames
        self.plotWidget.clear()
        for names in self.data.keys():
            self.legendItem.removeItem(names)
        for dname in self.selDataNames:
            self.plotWidget.addItem(self.data[dname])
            if self.errorbarCheckBox.isChecked() and self.yerr[dname]:
                self.plotWidget.addItem(self.dataErrPos[dname])
                self.plotWidget.addItem(self.dataErrNeg[dname])
                self.plotWidget.addItem(self.dataErr[dname])
                self.dataErr[dname].setCurves(self.dataErrPos[dname],self.dataErrNeg[dname])
            self.legendItem.addItem(self.data[dname],dname)
            
    def updatePlot(self):
        for dname in self.selDataNames:
            color=self.data[dname].opts['pen'].color()
            self.data[dname].setPen(pg.mkPen(color=color,width=float(self.lineWidthLineEdit.text())))
            self.data[dname].setSymbolSize(float(self.pointSizeLineEdit.text()))
        self.Plot(self.selDataNames)
            
    def setXLabel(self,label,fontsize=4):
        """
        sets the X-label of the plot
        """
        self.plotWidget.getPlotItem().setLabel('bottom','<font size='+str(fontsize)+'>'+label+'</font>')
            
    def setYLabel(self,label,fontsize=4):
        """
        sets the y-label of the plot
        """
        self.plotWidget.getPlotItem().setLabel('left','<font size='+str(fontsize)+'>'+label+'</font>')        
            
            
    def setTitle(self,title,fontsize=6):
        """
        Sets the y-label of the plot
        """
        self.plotWidget.getPlotItem().setTitle(title='<font size='+str(fontsize)+'>'+title+'</font>')
    