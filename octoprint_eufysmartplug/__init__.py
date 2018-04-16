# coding=utf-8
from __future__ import absolute_import


import octoprint.plugin
from octoprint.server import user_permission
from Crypto.Cipher import AES
import octoprint_eufysmartplug.lakeside_proto
import socket
import json
import logging
import os
import random
import re
import requests
import threading
import time
import struct


key = bytearray([0x24, 0x4E, 0x6D, 0x8A, 0x56, 0xAC, 0x87, 0x91, 0x24, 0x43, 0x2D, 0x8B, 0x6C, 0xBC, 0xA2, 0xC4])
iv = bytearray([0x77, 0x24, 0x56, 0xF2, 0xA7, 0x66, 0x4C, 0xF3, 0x39, 0x2C, 0x35, 0x97, 0xE9, 0x3E, 0x57, 0x47])


class eufysmartplugPlugin(octoprint.plugin.SettingsPlugin,
                            octoprint.plugin.AssetPlugin,
                            octoprint.plugin.TemplatePlugin,
							octoprint.plugin.SimpleApiPlugin,
							octoprint.plugin.StartupPlugin):
							
	def __init__(self):
		self._logger = logging.getLogger("octoprint.plugins.eufysmartplug")
		self._eufysmartplug_logger = logging.getLogger("octoprint.plugins.eufysmartplug.debug")
							
	##~~ StartupPlugin mixin
	
	def on_startup(self, host, port):
		# setup customized logger
		from octoprint.logging.handlers import CleaningTimedRotatingFileHandler
		eufysmartplug_logging_handler = CleaningTimedRotatingFileHandler(self._settings.get_plugin_logfile_path(postfix="debug"), when="D", backupCount=3)
		eufysmartplug_logging_handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s"))
		eufysmartplug_logging_handler.setLevel(logging.DEBUG)

		self._eufysmartplug_logger.addHandler(eufysmartplug_logging_handler)
		self._eufysmartplug_logger.setLevel(logging.DEBUG if self._settings.get_boolean(["debug_logging"]) else logging.INFO)
		self._eufysmartplug_logger.propagate = False
	
	def on_after_startup(self):
		self._logger.info("EufySmartplug loaded!")
	
	##~~ SettingsPlugin mixin
	
	def get_settings_defaults(self):
		return dict(
			debug_logging = False,
			arrSmartplugs = [{'ip':'','id':'','type':'','label':'','icon':'icon-bolt','displayWarning':True,'warnPrinting':False,'gcodeEnabled':False,'gcodeOnDelay':0,'gcodeOffDelay':0,'autoConnect':True,'autoConnectDelay':10.0,'autoDisconnect':True,'autoDisconnectDelay':0,'sysCmdOn':False,'sysRunCmdOn':'','sysCmdOnDelay':0,'sysCmdOff':False,'sysRunCmdOff':'','sysCmdOffDelay':0,'currentState':'unknown','btnColor':'#808080'}],
			pollingInterval = 15,
			pollingEnabled = False
		)
		
	def on_settings_save(self, data):	
		old_debug_logging = self._settings.get_boolean(["debug_logging"])

		octoprint.plugin.SettingsPlugin.on_settings_save(self, data)

		new_debug_logging = self._settings.get_boolean(["debug_logging"])
		if old_debug_logging != new_debug_logging:
			if new_debug_logging:
				self._eufysmartplug_logger.setLevel(logging.DEBUG)
			else:
				self._eufysmartplug_logger.setLevel(logging.INFO)
				
	def get_settings_version(self):
		return 4
		
	def on_settings_migrate(self, target, current=None):
		if current is None or current < self.get_settings_version():
			# Reset plug settings to defaults.
			self._logger.debug("Resetting arrSmartplugs for eufysmartplug settings.")
			self._settings.set(['arrSmartplugs'], self.get_settings_defaults()["arrSmartplugs"])
		
	##~~ AssetPlugin mixin

	def get_assets(self):
		return dict(
			js=["js/eufysmartplug.js"],
			css=["css/eufysmartplug.css"]
		)
		
	##~~ TemplatePlugin mixin
	
	def get_template_configs(self):
		return [
			dict(type="navbar", custom_bindings=True),
			dict(type="settings", custom_bindings=True)
		]
		
	##~~ SimpleApiPlugin mixin
	
	def turn_on(self, plugip):
		self._eufysmartplug_logger.debug("Turning on %s." % plugip)
		plug = self.plug_search(self._settings.get(["arrSmartplugs"]),"ip",plugip)
		self._eufysmartplug_logger.debug(plug)		
		chk = self.sendCommand("on",plug)
		if chk == 1:
			self.check_status(plugip)
			if plug["autoConnect"]:
				t = threading.Timer(int(plug["autoConnectDelay"]),self._printer.connect)
				t.start()
			if plug["sysCmdOn"]:
				t = threading.Timer(int(plug["sysCmdOnDelay"]),os.system,args=[plug["sysRunCmdOn"]])
				t.start()
	
	def turn_off(self, plugip):
		self._eufysmartplug_logger.debug("Turning off %s." % plugip)
		plug = self.plug_search(self._settings.get(["arrSmartplugs"]),"ip",plugip)
		self._eufysmartplug_logger.debug(plug)
		if plug["sysCmdOff"]:
			t = threading.Timer(int(plug["sysCmdOffDelay"]),os.system,args=[plug["sysRunCmdOff"]])
			t.start()			
		if plug["autoDisconnect"]:
			self._printer.disconnect()
			time.sleep(int(plug["autoDisconnectDelay"]))
		chk = self.sendCommand("off",plug)
		if chk == 0:
			self.check_status(plugip)
		
	def check_status(self, plugip):
		self._eufysmartplug_logger.debug("Checking status of %s." % plugip)
		if plugip != "":
			plug = self.plug_search(self._settings.get(["arrSmartplugs"]),"ip",plugip)
			chk = self.sendCommand("info",plug)
			if chk == 1:
				self._plugin_manager.send_plugin_message(self._identifier, dict(currentState="on",ip=plugip))
			elif chk == 0:
				self._plugin_manager.send_plugin_message(self._identifier, dict(currentState="off",ip=plugip))
			else:
				self._eufysmartplug_logger.debug(response)
				self._plugin_manager.send_plugin_message(self._identifier, dict(currentState="unknown",ip=plugip))		
	
	def get_api_commands(self):
		return dict(turnOn=["ip"],turnOff=["ip"],checkStatus=["ip"])

	def on_api_command(self, command, data):
		if not user_permission.can():
			from flask import make_response
			return make_response("Insufficient rights", 403)
        
		if command == 'turnOn':
			self.turn_on("{ip}".format(**data))
		elif command == 'turnOff':
			self.turn_off("{ip}".format(**data))
		elif command == 'checkStatus':
			self.check_status("{ip}".format(**data))
			
	##~~ Utilities
	
	def plug_search(self, list, key, value): 
		for item in list: 
			if item[key] == value: 
				return item
	
	def sendCommand(self, cmd, plug):	
		commands = {
			'on'       : 1,
			'off'      : 0,
		}
		
				
		try:
			plugdev = switch(plug["ip"],plug["id"],plug["type"])
			plugdev.connect()
      			if cmd != 'info':
				plugdev.set_state(power = commands[cmd])
                        return plugdev.get_status().switchinfo.packet.switchstatus.power
		except socket.error:
			return -1	
	##~~ Gcode processing hook
	
	def processGCODE(self, comm_instance, phase, cmd, cmd_type, gcode, *args, **kwargs):
		if gcode:
			if cmd.startswith("M80"):			
				plugip = re.sub(r'^M80\s?', '', cmd)
				self._eufysmartplug_logger.debug("Received M80 command, attempting power on")
				plug = self.plug_search(self._settings.get(["arrSmartplugs"]),"ip",plugip)
                                if plug is None:
					plug = self.plug_search(self._settings.get(["arrSmartplugs"]),"gcodeEnabled",True)
                                if plug is not None:
					self._eufysmartplug_logger.debug(plug)
					if plug["gcodeEnabled"]:
						t = threading.Timer(int(plug["gcodeOnDelay"]),self.turn_on,args=[plug["ip"]])
						t.start()
				return
			elif cmd.startswith("M81"):
				plugip = re.sub(r'^M81\s?', '', cmd)
				self._eufysmartplug_logger.debug("Received M81 command, attempting power off")
				plug = self.plug_search(self._settings.get(["arrSmartplugs"]),"ip",plugip)
                                if plug is None:
					plug = self.plug_search(self._settings.get(["arrSmartplugs"]),"gcodeEnabled",True)
				if plug is not None:
					self._eufysmartplug_logger.debug(plug)
					if plug["gcodeEnabled"]:
						t = threading.Timer(int(plug["gcodeOffDelay"]),self.turn_off,args=[plug["ip"]])
						t.start()
				return
			else:
				return
			

	##~~ Softwareupdate hook

	def get_update_information(self):
		# Define the configuration for your plugin to use with the Software Update
		# Plugin here. See https://github.com/foosel/OctoPrint/wiki/Plugin:-Software-Update
		# for details.
		return dict(
			eufysmartplug=dict(
				displayName="Eufy Smartplug",
				displayVersion=self._plugin_version,

				# version check: github repository
				type="github_release",
				user="Desterly",
				repo="OctoPrint-EufySmartplug",
				current=self._plugin_version,

				# update method: pip
				pip="https://github.com/Desterly/OctoPrint-EufySmartplug/archive/{target_version}.zip"
			)
		)


class device:
    def __init__(self, address, code, kind=None):
        self.address = address
        self.code = code
        self.kind = kind
        
    def connect(self):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.connect((self.address, 55556))
        self.update()
        
    def send_packet(self, packet, response):
        cipher = AES.new(bytes(key), AES.MODE_CBC, bytes(iv))
        raw_packet = packet.SerializeToString()
    
        for i in range(16 - (len(raw_packet) % 16)):
            raw_packet += b'\0'
        
        encrypted_packet = cipher.encrypt(raw_packet)
      
        self.s.send(encrypted_packet)
        if response:
            data = self.s.recv(1024)
     
            cipher = AES.new(bytes(key), AES.MODE_CBC, bytes(iv))
            decrypted_packet = cipher.decrypt(data)
        
            length = struct.unpack("<H", decrypted_packet[0:2])[0]
            if self.kind == "T1011" or self.kind == "T1012":
                packet.ParseFromString(decrypted_packet[2:length+2])
            elif self.kind == "T1013":
                packet = octoprint_eufysmartplug.lakeside_proto.T1013Packet()
                packet.ParseFromString(decrypted_packet[2:length+2])
            elif self.kind == "T1201" or self.kind == "T1202" or self.kind == "T1211":
                packet = octoprint_eufysmartplug.lakeside_proto.T1201Packet()
                packet.ParseFromString(decrypted_packet[2:length+2])
            return packet
        
        return None
        
    def get_sequence(self):
        packet = octoprint_eufysmartplug.lakeside_proto.T1012Packet()
        packet.sequence = random.randrange(3000000)
        packet.code = self.code
        packet.ping.type = 0
        response = self.send_packet(packet, True)
        return response.sequence + 1
    
class switch(device):
    def __init__(self, address, code, kind):
        return device.__init__(self, address, code, kind)
        
    def connect(self):
        return device.connect(self)
        
    def send_packet(self, packet, response):
        return device.send_packet(self, packet, response)
        
    def get_sequence(self):
        return device.get_sequence(self)
        
    def get_status(self):
        packet = octoprint_eufysmartplug.lakeside_proto.T1201Packet()
        packet.sequence = self.get_sequence()
        packet.code = self.code
        packet.switchinfo.type = 1
        response = self.send_packet(packet, True)
        return response
        
    def update(self):
        response = self.get_status()
        self.power = response.switchinfo.packet.switchstatus.power
        
    def set_state(self, power):
        packet = octoprint_eufysmartplug.lakeside_proto.T1201Packet()
        packet.switchinfo.type = 0
        packet.switchinfo.packet.unknown1 = 100
        packet.switchinfo.packet.switchset.command = 7
        packet.switchinfo.packet.switchset.state = power
        packet.sequence = self.get_sequence()
        packet.code = self.code
        self.send_packet(packet, False)            
        
# If you want your plugin to be registered within OctoPrint under a different name than what you defined in setup.py
# ("OctoPrint-PluginSkeleton"), you may define that here. Same goes for the other metadata derived from setup.py that
# can be overwritten via __plugin_xyz__ control properties. See the documentation for that.
__plugin_name__ = "Eufy Smartplug"

def __plugin_load__():
	global __plugin_implementation__
	__plugin_implementation__ = eufysmartplugPlugin()

	global __plugin_hooks__
	__plugin_hooks__ = {
		"octoprint.comm.protocol.gcode.queuing": __plugin_implementation__.processGCODE,
		"octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
	}

