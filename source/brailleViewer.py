#brailleViewer.py
#A part of NonVisual Desktop Access (NVDA)
#Copyright (C) 2014-2017 NV Access Limited
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.

import wx
import gui
import braille
from braille import BrailleDisplayDriver
import inputCore
from logHandler import log

# global callbacks for braille viewer creation and destruction.
_callbacks = []

# global braille viewer driver:
_display = None

def isBrailleDisplayCreated():
	return bool(_display)

# I suspect this could keep objects alive longer than intended
# or cause object deletion order problems. Need to look into the
# iodomaitic pattern for handling this in python.
# would a week reference to the callback mean that the deregister func
# no longer needs to be called?
BRAILLE_DISPLAY_DESTROYED = 0
BRAILLE_DISPLAY_CREATED = 1
def registerCallbackAndCallNow(onBrailleDisplayChangeState):
	_callbacks.append(onBrailleDisplayChangeState)
	# call function now to set initial state.
	onBrailleDisplayChangeState(BRAILLE_DISPLAY_CREATED if isBrailleDisplayCreated() else BRAILLE_DISPLAY_DESTROYED)

def deregisterCallback(onBrailleDisplayChangeState):
	_callbacks.remove(onBrailleDisplayChangeState)

def _doCallBacks(evt):
	for x in _callbacks:
		x(evt)

def getBrailleViewerTool():
	return _display

def toggleBrailleViewerTool():
	if isBrailleDisplayCreated():
		destroyBrailleViewerTool()
	else:
		createBrailleViewerTool()

def destroyBrailleViewerTool():
	log.debug("reef destroyBrailleViewerTool")
	global _display
	if not _display:
		return
	try:
		_display.terminate()
	except:
		log.error("Error terminating braille viewer tool", exc_info=True)
	_display = None
	_doCallBacks(BRAILLE_DISPLAY_DESTROYED)

DEFAULT_NUM_CELLS = 40
def createBrailleViewerTool():
	if not gui.mainFrame:
		raise RuntimeError("Can not initialise the BrailleViewerGui: gui.mainFrame not yet initialised")
	if not braille.handler:
		raise RuntimeError("Can not initialise the BrailleViewerGui: braille.handler not yet initialised")

	cells = DEFAULT_NUM_CELLS if not braille.handler.displaySize else braille.handler.displaySize
	global _display
	if _display:
		d = _display
		destroyBrailleViewerTool()
		_display = d
		_display.__init__(cells)
	else:
		_display = BrailleViewerDriver(cells)
	_doCallBacks(BRAILLE_DISPLAY_CREATED)

BRAILLE_UNICODE_PATTERNS_START = 0x2800
SPACE_CHARACTER = u" "

class BrailleViewerFrame(wx.MiniFrame):

	def __init__(self, numCells, onCloseFunc):
		super(BrailleViewerFrame, self).__init__(gui.mainFrame, wx.ID_ANY, _("NVDA Braille Viewer"), style=wx.CAPTION | wx.RESIZE_BORDER | wx.STAY_ON_TOP)
		self._notifyOfClose = onCloseFunc
		self.Bind(wx.EVT_CLOSE, self.onClose)
		self.lastBraille = SPACE_CHARACTER * numCells
		self.lastText = SPACE_CHARACTER
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		item = self.output = wx.StaticText(self, label=self.lastBraille)
		item.Font = self.setFont(item.GetFont(), forBraille=True)
		mainSizer.Add(item, flag=wx.EXPAND)

		item = self.rawoutput = wx.StaticText(self, label=SPACE_CHARACTER)
		item.Font = self.setFont(item.Font)
		mainSizer.Add(item, flag=wx.EXPAND)
		mainSizer.Fit(self)
		self.Sizer = mainSizer
		self.Show()

	def updateValues(self, braille, text):
		brailleEqual = self.lastBraille == braille
		textEqual = self.lastText == text
		if brailleEqual and textEqual:
			return
		self.Freeze()
		if not brailleEqual:
			self.output.Label = self.lastBraille = braille
		if not textEqual:
			self.rawoutput.Label = self.lastText = text
		self.Thaw()
		self.Refresh()
		self.Update()

	def setFont(self, font, forBraille=False):
		# Braille characters are much smaller than the raw text characters, override the size
		# I assume this is because the "Courier New" font does not support this unicode range
		# so the system falls back to another font.
		font.PointSize = 20 if not forBraille else 22
		font.Family = wx.FONTFAMILY_TELETYPE
		font.FaceName = "Courier New"
		return font

	def onClose(self, evt):
		log.debug("reef onClose")
		if not evt.CanVeto():
			self._notifyOfClose()
			self.Destroy()
			return
		evt.Veto()

	def close(self):
		self.Destroy()

class BrailleViewerDriver(BrailleDisplayDriver):
	name = "brailleViewer"
	description = _("Braille viewer")
	numCells = DEFAULT_NUM_CELLS # Overriden to match an active braille display
	_brailleGui = None # A BrailleViewer instance

	@classmethod
	def check(cls):
		return True

	def __init__(self, numCells):
		super(BrailleViewerDriver, self).__init__()
		self.numCells = numCells
		self.rawText = u""
		self._setupBrailleGui()

	def _setupBrailleGui(self):
		# check we have not initialialised yet
		if self._brailleGui:
			return True
		self._brailleGui = BrailleViewerFrame(self.numCells, destroyBrailleViewerTool)

	def display(self, cells):
		if not self._setupBrailleGui():
			return
		brailleUnicodeChars = (unichr(BRAILLE_UNICODE_PATTERNS_START + cell) for cell in cells)
		# replace braille "space" with regular space because the width of the braille space
		# does not match the other braille characters, the result is better, but not perfect.
		brailleSpace = unichr(BRAILLE_UNICODE_PATTERNS_START)
		spaceReplaced = (cell.replace(brailleSpace, SPACE_CHARACTER) for cell in brailleUnicodeChars)
		self._brailleGui.updateValues(u"".join(spaceReplaced), self.rawText)

	def terminate(self):
		log.debug("reef terminate")
		super(BrailleViewerDriver, self).terminate()
		try:
			self._brailleGui.Destroy()
			self._brailleGui = None
		except wx.PyDeadObjectError:
			# NVDA's GUI has already terminated.
			pass
