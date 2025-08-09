# =============================================================================
# GSM HANDLER - SIM800L COMMUNICATION
# =============================================================================
# File: gsm_handler.py
# Description: SIM800L GSM module communication for SMS and data transmission

import machine
import utime
import re
from config import *

class GSMHandler:
    def __init__(self):
        """Initialize SIM800L GSM module"""
        # Software UART for SIM800L communication
        self.uart = machine.UART(0, baudrate=UART_BAUDRATE,
                                tx=machine.Pin(GSM_TX_PIN),
                                rx=machine.Pin(GSM_RX_PIN))
        
        # Module status tracking
        self.module_ready = False
        self.network_registered = False
        self.sms_ready = False
        self.gprs_connected = False
        
        # Connection parameters
        self.signal_strength = 0
        self.operator = ""
        
        # SMS tracking
        self.sms_sent_count = 0
        self.sms_failed_count = 0
        self.last_sms_time = 0
        
        # Initialize module
        self.initialize_module()
        
        print("GSM Handler initialized")
    
    def send_at_command(self, command, expected_response="OK", timeout=10):
        """Send AT command to SIM800L and wait for response"""
        try:
            # Clear UART buffer
            while self.uart.any():
                self.uart.read()
            
            # Send command
            full_command = command + '\r\n'
            self.uart.write(full_command.encode())
            
            # Wait for response
            start_time = utime.time()
            response = ""
            
            while utime.time() - start_time < timeout:
                if self.uart.any():
                    data = self.uart.read()
                    if data:
                        response += data.decode('utf-8', errors='ignore')
                        
                        # Check if expected response received
                        if expected_response in response:
                            return True, response
                        
                        # Check for error responses
                        if "ERROR" in response or "FAIL" in response:
                            return False, response
                
                utime.sleep_ms(100)
            
            # Timeout occurred
            return False, response
            
        except Exception as e:
            print(f"AT command error: {e}")
            return False, str(e)
    
    def initialize_module(self):
        """Initialize SIM800L module with basic settings"""
        print("Initializing SIM800L module...")
        
        # Wait for module to boot up
        utime.sleep(3)
        
        initialization_steps = [
            ("AT", "OK", "Basic communication test"),
            ("ATE0", "OK", "Disable echo"),
            ("AT+CMEE=2", "OK", "Enable extended error reporting"),
            ("AT+CREG?", "+CREG:", "Check network registration"),
            ("AT+CSQ", "+CSQ:", "Check signal strength"),
            ("AT+COPS?", "+COPS:", "Check network operator"),
            ("AT+CMGF=1", "OK", "Set SMS text mode"),
            ("AT+CSCS=\"GSM\"", "OK", "Set character set"),
            ("AT+CNMI=1,2,0,0,0", "OK", "Configure SMS notifications")
        ]
        
        for command, expected, description in initialization_steps:
            print(f"  {description}...")
            success, response = self.send_at_command(command, expected, 10)
            
            if success:
                print(f"    ✓ {command} - OK")
                
                # Parse specific responses
                if command == "AT+CSQ":
                    self.parse_signal_strength(response)
                elif command == "AT+COPS?":
                    self.parse_operator(response)
                elif command == "AT+CREG?":
                    self.parse_network_status(response)
                    
            else:
                print(f"    ✗ {command} - Failed: {response}")
                
            utime.sleep(1)
        
        # Final status check
        self.check_module_status()
        
        if self.module_ready:
            print("SIM800L initialization successful!")
        else:
            print("SIM800L initialization failed - some features may not work")
    
    def parse_signal_strength(self, response):
        """Parse signal strength from AT+CSQ response"""
        try:
            match = re.search(r'\+CSQ: (\d+),(\d+)', response)
            if match:
                rssi = int(match.group(1))
                if rssi == 99:
                    self.signal_strength = 0  # Unknown
                elif rssi >= 20:
                    self.signal_strength = 5  # Excellent
                elif rssi >= 15:
                    self.signal_strength = 4  # Good
                elif rssi >= 10:
                    self.signal_strength = 3  # Fair
                elif rssi >= 5:
                    self.signal_strength = 2  # Marginal
                else:
                    self.signal_strength = 1  # Poor
                    
                print(f"    Signal strength: {self.signal_strength}/5 (RSSI: {rssi})")
        except:
            pass
    
    def parse_operator(self, response):
        """Parse network operator from AT+COPS response"""
        try:
            match = re.search(r'"([^"]+)"', response)
            if match:
                self.operator = match.group(1)
                print(f"    Network operator: {self.operator}")
        except:
            pass
    
    def parse_network_status(self, response):
        """Parse network registration status"""
        try:
            match = re.search(r'\+CREG: \d+,(\d+)', response)
            if match:
                status = int(match.group(1))
                if status in [1, 5]:  # Registered (home/roaming)
                    self.network_registered = True
                    print(f"    Network: Registered")
                else:
                    self.network_registered = False
                    print(f"    Network: Not registered (status: {status})")
        except:
            pass
    
    def check_module_status(self):
        """Check overall module status"""
        # Basic communication test
        success, _ = self.send_at_command("AT", "OK", 5)
        
        if success and self.network_registered and self.signal_strength > 0:
            self.module_ready = True
            self.sms_ready = True
        else:
            self.module_ready = False
            self.sms_ready = False
    
    def send_sms(self, recipients, message):
        """Send SMS to multiple recipients"""
        if not self.sms_ready:
            print("SMS not ready - checking module status...")
            self.check_module_status()
            if not self.sms_ready:
                return False
        
        # Rate limiting - don't send SMS too frequently
        current_time = utime.time()
        if current_time - self.last_sms_time < 30:  # 30 seconds minimum between SMS
            print("SMS rate limited - waiting...")
            return False
        
        success_count = 0
        
        # Send to each recipient
        for recipient in recipients:
            if self.send_single_sms(recipient, message):
                success_count += 1
                self.sms_sent_count += 1
            else:
                self.sms_failed_count += 1
            
            # Delay between messages
            utime.sleep(2)
        
        self.last_sms_time = current_time
        
        print(f"SMS sent to {success_count}/{len(recipients)} recipients")
        return success_count > 0
    
    def send_single_sms(self, number, message):
        """Send SMS to a single recipient"""
        try:
            print(f"Sending SMS to {number}...")
            
            # Set SMS recipient
            command = f'AT+CMGS="{number}"'
            success, response = self.send_at_command(command, ">", 10)
            
            if not success:
                print(f"Failed to set SMS recipient: {response}")
                return False
            
            # Send message content
            message_with_ctrl_z = message + chr(26)  # Ctrl+Z to send
            self.uart.write(message_with_ctrl_z.encode())
            
            # Wait for confirmation
            start_time = utime.time()
            response = ""
            
            while utime.time() - start_time < 30:  # 30 second timeout for SMS
                if self.uart.any():
                    data = self.uart.read()
                    if data:
                        response += data.decode('utf-8', errors='ignore')
                        
                        if "+CMGS:" in response:
                            print(f"  ✓ SMS sent successfully to {number}")
                            return True
                        
                        if "ERROR" in response:
                            print(f"  ✗ SMS failed to {number}: {response}")
                            return False
                
                utime.sleep_ms(500)
            
            print(f"  ✗ SMS timeout to {number}")
            return False
            
        except Exception as e:
            print(f"SMS send error to {number}: {e}")
            return False
    
    def send_threshold_alert(self, tenant, alert_type, value, threshold):
        """Send specific threshold alert SMS"""
        current_time = utime.localtime()
        timestamp = f"{current_time[2]:02d}/{current_time[1]:02d}/{current_time[0]} {current_time[3]:02d}:{current_time[4]:02d}"
        
        if alert_type == "energy":
            message = f"⚠️ ENERGY ALERT ⚠️\n"
            message += f"Time: {timestamp}\n"
            message += f"Tenant {tenant}: {value:.1f}kWh\n"
            message += f"Limit: {threshold:.1f}kWh\n"
            message += f"Exceeded by: {value - threshold:.1f}kWh\n"
            message += f"Please reduce usage."
        else:  # cost alert
            message = f"⚠️ COST ALERT ⚠️\n"
            message += f"Time: {timestamp}\n"
            message += f"Tenant {tenant}: ₵{value:.2f}\n"
            message += f"Limit: ₵{threshold:.2f}\n"
            message += f"Exceeded by: ₵{value - threshold:.2f}\n"
            message += f"Please reduce usage."
        
        return self.send_sms(SMS_RECIPIENTS, message)
    
    def send_daily_report(self, tenant_a_data, tenant_b_data):
        """Send daily energy consumption report"""
        current_time = utime.localtime()
        date = f"{current_time[2]:02d}/{current_time[1]:02d}/{current_time[0]}"
        
        message = f"📊 DAILY ENERGY REPORT\n"
        message += f"Date: {date}\n\n"
        message += f"TENANT A:\n"
        message += f"  Energy: {tenant_a_data['energy']:.1f}kWh\n"
        message += f"  Cost: ₵{tenant_a_data['cost']:.2f}\n\n"
        message += f"TENANT B:\n"
        message += f"  Energy: {tenant_b_data['energy']:.1f}kWh\n"
        message += f"  Cost: ₵{tenant_b_data['cost']:.2f}\n\n"
        
        total_energy = tenant_a_data['energy'] + tenant_b_data['energy']
        total_cost = tenant_a_data['cost'] + tenant_b_data['cost']
        
        message += f"TOTAL:\n"
        message += f"  Energy: {total_energy:.1f}kWh\n"
        message += f"  Cost: ₵{total_cost:.2f}\n\n"
        message += f"Monitor: bit.ly/energy-dashboard"
        
        return self.send_sms(SMS_RECIPIENTS, message)
    
    def send_system_alert(self, error_message):
        """Send system error alert SMS"""
        current_time = utime.localtime()
        timestamp = f"{current_time[2]:02d}/{current_time[1]:02d}/{current_time[0]} {current_time[3]:02d}:{current_time[4]:02d}"
        
        message = f"🔧 SYSTEM ALERT\n"
        message += f"Time: {timestamp}\n"
        message += f"Error: {error_message}\n"
        message += f"Check device immediately."
        
        return self.send_sms(SMS_RECIPIENTS, message)
    
    def setup_gprs(self, apn="internet"):
        """Setup GPRS connection for data transmission"""
        print("Setting up GPRS connection...")
        
        gprs_commands = [
            ("AT+SAPBR=3,1,\"CONTYPE\",\"GPRS\"", "OK", "Set connection type"),
            (f"AT+SAPBR=3,1,\"APN\",\"{apn}\"", "OK", "Set APN"),
            ("AT+SAPBR=1,1", "OK", "Open GPRS context"),
            ("AT+SAPBR=2,1", "+SAPBR: 1,1", "Check GPRS status")
        ]
        
        for command, expected, description in gprs_commands:
            print(f"  {description}...")
            success, response = self.send_at_command(command, expected, 15)
            
            if success:
                print(f"    ✓ {description} - OK")
            else:
                print(f"    ✗ {description} - Failed: {response}")
                return False
            
            utime.sleep(2)
        
        self.gprs_connected = True
        print("GPRS connection established!")
        return True
    
    def send_http_request(self, url, data=None):
        """Send HTTP request via GPRS"""
        if not self.gprs_connected:
            if not self.setup_gprs():
                return False, "GPRS not available"
        
        try:
            # Initialize HTTP service
            success, _ = self.send_at_command("AT+HTTPINIT", "OK", 10)
            if not success:
                return False, "HTTP init failed"
            
            # Set HTTP parameters
            self.send_at_command("AT+HTTPPARA=\"CID\",1", "OK", 5)
            self.send_at_command(f"AT+HTTPPARA=\"URL\",\"{url}\"", "OK", 5)
            
            if data:
                # POST request with data
                self.send_at_command("AT+HTTPPARA=\"CONTENT\",\"application/x-www-form-urlencoded\"", "OK", 5)
                self.send_at_command(f"AT+HTTPDATA={len(data)},10000", "DOWNLOAD", 10)
                
                # Send data
                self.uart.write(data.encode())
                utime.sleep(2)
                
                # Execute POST
                success, response = self.send_at_command("AT+HTTPACTION=1", "+HTTPACTION: 1,200", 30)
            else:
                # GET request
                success, response = self.send_at_command("AT+HTTPACTION=0", "+HTTPACTION: 0,200", 30)
            
            # Terminate HTTP service
            self.send_at_command("AT+HTTPTERM", "OK", 5)
            
            return success, response
            
        except Exception as e:
            self.send_at_command("AT+HTTPTERM", "OK", 5)  # Cleanup
            return False, str(e)
    
    def get_status(self):
        """Get comprehensive GSM module status"""
        return {
            'module_ready': self.module_ready,
            'network_registered': self.network_registered,
            'sms_ready': self.sms_ready,
            'gprs_connected': self.gprs_connected,
            'signal_strength': self.signal_strength,
            'operator': self.operator,
            'sms_sent': self.sms_sent_count,
            'sms_failed': self.sms_failed_count
        }
    
    def close(self):
        """Close GSM module and cleanup"""
        try:
            # Close GPRS if connected
            if self.gprs_connected:
                self.send_at_command("AT+SAPBR=0,1", "OK", 10)
            
            # Deinitialize UART
            self.uart.deinit()
            print("GSM Handler closed")
            
        except Exception as e:
            print(f"GSM close error: {e}")
