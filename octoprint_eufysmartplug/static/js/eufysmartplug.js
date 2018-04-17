/*
 * View model for OctoPrint-EufySmartplug
 *
 * Author: Desterly
 * License: AGPLv3
 */
$(function() {
    function eufysmartplugViewModel(parameters) {
        var self = this;

        self.settings = parameters[0];
		self.loginState = parameters[1];

		self.arrSmartplugs = ko.observableArray();
		self.eufyHome = ko.observable();
		self.isPrinting = ko.observable(false);
		self.selectedPlug = ko.observable();
		self.processing = ko.observableArray([]);

		self.onBeforeBinding = function() {
			self.arrSmartplugs(self.settings.settings.plugins.eufysmartplug.arrSmartplugs());
        }

		self.onAfterBinding = function() {
			self.checkStatuses();
		}

        self.onEventSettingsUpdated = function(payload) {
			self.arrSmartplugs(self.settings.settings.plugins.eufysmartplug.arrSmartplugs());
		}

		self.onEventPrinterStateChanged = function(payload) {
			if (payload.state_id == "PRINTING" || payload.state_id == "PAUSED"){
				self.isPrinting(true);
			} else {
				self.isPrinting(false);
			}
		}

		self.cancelClick = function(data) {
			self.processing.remove(data.ip());
		}

		self.downloadPlug = function(data) {
			self.eufyHome({'username':ko.observable(''),
					'password':ko.observable('')
			});
			$("#EufyHomeEditor").modal("show");
		}

		self.downloadEufy = function(data) {

			$.ajax({
				url: API_BASEURL + "plugin/eufysmartplug",
				type: "POST",
				dataType: "json",
				data: JSON.stringify({
					command: "eufyDownload",
					username: data.username(),
					password: data.password()
				}),
				contentType: "application/json; charset=UTF-8",
				success: function(data) {
					self.settings.settings.plugins.eufysmartplug.arrSmartplugs.removeAll();
					//var array = [];
					$.each(data, function (index, value) {
						self.selectedPlug({'ip':ko.observable(value['ip']),
                                    'id':ko.observable(value['id']),
                                    'type':ko.observable(value['type']),
									'label':ko.observable(value['label']),
									'icon':ko.observable(value['icon']),
									'displayWarning':ko.observable(value['displayWarning']),
									'warnPrinting':ko.observable(value['warnPrinting']),
									'gcodeEnabled':ko.observable(value['gcodeEnabled']),
									'gcodeOnDelay':ko.observable(value['gcodeOnDelay']),
									'gcodeOffDelay':ko.observable(value['gcodeOffDelay']),
									'autoConnect':ko.observable(value['autoConnect']),
									'autoConnectDelay':ko.observable(value['autoConnectDelay']),
									'autoDisconnect':ko.observable(value['autoDisconnect']),
									'autoDisconnectDelay':ko.observable(value['autoDisconnectDelay']),
									'sysCmdOn':ko.observable(value['sysCmdOn']),
									'sysRunCmdOn':ko.observable(value['sysRunCmdOn']),
									'sysCmdOnDelay':ko.observable(value['sysCmdOnDelay']),
									'sysCmdOff':ko.observable(value['sysCmdOff']),
									'sysRunCmdOff':ko.observable(value['sysRunCmdOff']),
									'sysCmdOffDelay':ko.observable(value['sysCmdOffDelay']),
									'currentState':ko.observable(value['currentState']),
									'btnColor':ko.observable('#808080')});
						self.settings.settings.plugins.eufysmartplug.arrSmartplugs.push(self.selectedPlug());
					});
					$("#EufyHomeEditor").modal("hide");
				}
			});

		}

		self.editPlug = function(data) {
			self.selectedPlug(data);
			$("#EufyPlugEditor").modal("show");
		}

		self.addPlug = function() {
			self.selectedPlug({'ip':ko.observable(''),
                                                                        'id':ko.observable(''),
                                                                        'type':ko.observable(''),
									'label':ko.observable(''),
									'icon':ko.observable('icon-bolt'),
									'displayWarning':ko.observable(true),
									'warnPrinting':ko.observable(false),
									'gcodeEnabled':ko.observable(false),
									'gcodeOnDelay':ko.observable(0),
									'gcodeOffDelay':ko.observable(0),
									'autoConnect':ko.observable(true),
									'autoConnectDelay':ko.observable(10.0),
									'autoDisconnect':ko.observable(true),
									'autoDisconnectDelay':ko.observable(0),
									'sysCmdOn':ko.observable(false),
									'sysRunCmdOn':ko.observable(''),
									'sysCmdOnDelay':ko.observable(0),
									'sysCmdOff':ko.observable(false),
									'sysRunCmdOff':ko.observable(''),
									'sysCmdOffDelay':ko.observable(0),
									'currentState':ko.observable('unknown'),
									'btnColor':ko.observable('#808080')});
			self.settings.settings.plugins.eufysmartplug.arrSmartplugs.push(self.selectedPlug());
			$("#EufyPlugEditor").modal("show");
		}

		self.removePlug = function(row) {
			self.settings.settings.plugins.eufysmartplug.arrSmartplugs.remove(row);
		}

		self.onDataUpdaterPluginMessage = function(plugin, data) {
            if (plugin != "eufysmartplug") {
                return;
            }

			plug = ko.utils.arrayFirst(self.settings.settings.plugins.eufysmartplug.arrSmartplugs(),function(item){
				return item.ip() === data.ip;
				}) || {'ip':data.ip,'currentState':'unknown','btnColor':'#808080'};

			if (plug.currentState != data.currentState) {
				plug.currentState(data.currentState)
				switch(data.currentState) {
					case "on":
						break;
					case "off":
						break;
					default:
						new PNotify({
							title: 'Eufy Smartplug Error',
							text: 'Status ' + plug.currentState() + ' for ' + plug.ip() + '. Double check IP Address\\Hostname in EufySmartplug Settings.',
							type: 'error',
							hide: true
							});
				self.settings.saveData();
				}
			}
			self.processing.remove(data.ip);
        };

		self.toggleRelay = function(data) {
			self.processing.push(data.ip());
			switch(data.currentState()){
				case "on":
					self.turnOff(data);
					break;
				case "off":
					self.turnOn(data);
					break;
				default:
					self.checkStatus(data.ip());
			}
		}

		self.turnOn = function(data) {
			if(data.sysCmdOn()){
				setTimeout(function(){self.sysCommand(data.sysRunCmdOn())},data.sysCmdOnDelay()*1000);
			}
			self.sendTurnOn(data);
		}

		self.sendTurnOn = function(data) {
            $.ajax({
                url: API_BASEURL + "plugin/eufysmartplug",
                type: "POST",
                dataType: "json",
                data: JSON.stringify({
                    command: "turnOn",
					ip: data.ip()
                }),
                contentType: "application/json; charset=UTF-8"
            });
        };

    	self.turnOff = function(data) {
			if((data.displayWarning() || (self.isPrinting() && data.warnPrinting())) && !$("#EufySmartPlugWarning").is(':visible')){
				self.selectedPlug(data);
				$("#EufySmartPlugWarning").modal("show");
			} else {
				$("#EufySmartPlugWarning").modal("hide");
				if(data.sysCmdOff()){
					setTimeout(function(){self.sysCommand(data.sysRunCmdOff())},data.sysCmdOffDelay()*1000);
				}
				self.sendTurnOff(data);
			}
        };

		self.sendTurnOff = function(data) {
			$.ajax({
			url: API_BASEURL + "plugin/eufysmartplug",
			type: "POST",
			dataType: "json",
			data: JSON.stringify({
				command: "turnOff",
				ip: data.ip()
			}),
			contentType: "application/json; charset=UTF-8"
			});
		}

		self.checkStatus = function(plugIP) {
            $.ajax({
                url: API_BASEURL + "plugin/eufysmartplug",
                type: "POST",
                dataType: "json",
                data: JSON.stringify({
                    command: "checkStatus",
					ip: plugIP
                }),
                contentType: "application/json; charset=UTF-8"
            }).done(function(){
				self.settings.saveData();
				});
        };

		self.disconnectPrinter = function() {
            $.ajax({
                url: API_BASEURL + "plugin/eufysmartplug",
                type: "POST",
                dataType: "json",
                data: JSON.stringify({
                    command: "disconnectPrinter"
                }),
                contentType: "application/json; charset=UTF-8"
            });
		}

		self.connectPrinter = function() {
            $.ajax({
                url: API_BASEURL + "plugin/eufysmartplug",
                type: "POST",
                dataType: "json",
                data: JSON.stringify({
                    command: "connectPrinter"
                }),
                contentType: "application/json; charset=UTF-8"
            });
		}

		self.sysCommand = function(sysCmd) {
            $.ajax({
                url: API_BASEURL + "plugin/eufysmartplug",
                type: "POST",
                dataType: "json",
                data: JSON.stringify({
                    command: "sysCommand",
					cmd: sysCmd
                }),
                contentType: "application/json; charset=UTF-8"
            });
		}

		self.checkStatuses = function() {
			ko.utils.arrayForEach(self.settings.settings.plugins.eufysmartplug.arrSmartplugs(),function(item){
				if(item.ip() !== "") {
					console.log("checking " + item.ip())
					self.checkStatus(item.ip());
				}
			});
			if (self.settings.settings.plugins.eufysmartplug.pollingEnabled()) {
				setTimeout(function() {self.checkStatuses();}, (parseInt(self.settings.settings.plugins.eufysmartplug.pollingInterval(),10) * 60000));
			};
        };
    }

    // view model class, parameters for constructor, container to bind to
    OCTOPRINT_VIEWMODELS.push([
        eufysmartplugViewModel,

        // e.g. loginStateViewModel, settingsViewModel, ...
        ["settingsViewModel","loginStateViewModel"],

        // "#navbar_plugin_eufysmartplug","#settings_plugin_eufysmartplug"
        ["#navbar_plugin_eufysmartplug","#settings_plugin_eufysmartplug"]
    ]);
});
