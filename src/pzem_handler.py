# =============================================================================
# PZEM-004T-100A SENSOR HANDLER (CORRECTED)
# =============================================================================
# File: pzem_handler.py
# Description: PZEM-004T-100A sensor communication and data processing

import machine
import utime
import struct
from config import *

class PZEMHandler:
    def __init__(self):
        """Initialize PZEM-004T-100A sensor communication"""
        # UART interfaces for both PZEM modules
        # Note: Each PZEM-004T-100A must have a unique Modbus address
        self.uart_a = machine.UART(0, baudrate=UART_BAUDRATE, 
                                   tx=machine.Pin(PZEM_A_TX_PIN), 
                                   rx=machine.Pin(PZEM_A_RX_PIN),
                                   bits=8, parity=None, stop=1,
                                   timeout=1000)
        
        self.uart_b = machine.UART(1, baudrate=UART_BAUDRATE,
                                   tx=machine.Pin(PZEM_B_TX_PIN),
                                   rx=machine.Pin(PZEM_B_RX_PIN),
                                   bits=8, parity=None, stop=1,
                                   timeout=1000)
        
        # Modbus addresses for each PZEM module
        self.address_a = 0x01  # First module address
        self.address_b = 0x02  # Second module address (must be different!)
        
        # Energy accumulators
        self.energy_a = 0.0
        self.energy_b = 0.0
        self.daily_energy_a = 0.0
        self.daily_energy_b = 0.0
        
        # Last reading timestamps
        self.last_reading_a = 0
        self.last_reading_b = 0
        
        print("PZEM-004T-100A sensors initialized")
        print(f"Module A: Address 0x{self.address_a:02X}")
        print(f"Module B: Address 0x{self.address_b:02X}")
    
    def crc16_modbus(self, data):
        """Calculate Modbus RTU CRC16"""
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc >>= 1
                    crc ^= 0xA001
                else:
                    crc >>= 1
        return crc
    
    def build_read_command(self, address):
        """Build Modbus RTU read command for PZEM-004T-100A"""
        # Modbus RTU frame for PZEM-004T-100A:
        # [Address][Function Code 0x04][Start Reg 0x0000][Num Regs 0x000A][CRC]
        command = bytearray([
            address,        # Device address
            0x04,          # Function code: Read Input Registers  
            0x00, 0x00,    # Starting register: 0x0000
            0x00, 0x0A     # Number of registers: 10 (20 bytes of data)
        ])
        
        # Calculate and append CRC16
        crc = self.crc16_modbus(command)
        command.append(crc & 0xFF)          # CRC low byte
        command.append((crc >> 8) & 0xFF)   # CRC high byte
        
        return bytes(command)
    
    def send_command(self, uart, address):
        """Send read command to PZEM-004T-100A module"""
        command = self.build_read_command(address)
        
        # Clear receive buffer
        while uart.any():
            uart.read()
        
        # Send command
        uart.write(command)
        utime.sleep_ms(100)  # Wait for response
    
    def read_response(self, uart, address, timeout_ms=500):
        """Read and parse PZEM-004T-100A response with timeout"""
        start = utime.ticks_ms()
        response = b''
        
        while utime.ticks_diff(utime.ticks_ms(), start) < timeout_ms:
            if uart.any():
                chunk = uart.read()
                if chunk:
                    response += chunk
                    # PZEM-004T-100A response is 25 bytes
                    if len(response) >= 25:
                        break
            utime.sleep_ms(10)
        
        if len(response) < 25:
            if response:
                print(f"Incomplete response from 0x{address:02X}: {len(response)} bytes")
            return None
        
        # Validate response
        if response[0] != address:
            print(f"Wrong address in response: got 0x{response[0]:02X}, expected 0x{address:02X}")
            return None
        
        if response[1] != 0x04:
            if response[1] == 0x84:  # Error response
                error_code = response[2] if len(response) > 2 else 0
                print(f"Modbus error from 0x{address:02X}: code 0x{error_code:02X}")
            else:
                print(f"Wrong function code from 0x{address:02X}: 0x{response[1]:02X}")
            return None
        
        if response[2] != 20:
            print(f"Wrong byte count from 0x{address:02X}: {response[2]}")
            return None
        
        # Verify CRC
        data_for_crc = response[:-2]
        calculated_crc = self.crc16_modbus(data_for_crc)
        received_crc = response[-2] | (response[-1] << 8)
        
        if calculated_crc != received_crc:
            print(f"CRC error from 0x{address:02X}: calc=0x{calculated_crc:04X}, recv=0x{received_crc:04X}")
            return None
        
        # Parse data
        try:
            data_bytes = response[3:23]  # 20 data bytes
            
            # Parse as big-endian 16-bit registers
            registers = []
            for i in range(0, 20, 2):
                reg = struct.unpack('>H', data_bytes[i:i+2])[0]
                registers.append(reg)

            # Extract measurements according to PZEM-004T-100A format/ datasheet
            voltage = registers[0] / 10.0                      # Reg 0: 0.1V resolution
            
            # Current is 32-bit across registers 1 & 2
            current_raw = (registers[2] << 16) | registers[1]  # Reg 1,2: Current (32-bit)
            current = current_raw / 1000.0

            # Power is 32-bit across registers 3 & 4
            power_raw = (registers[4] << 16) | registers[3]    # Reg 3,4: Power (32-bit)
            power = power_raw / 10.0                           # Convert to watts

            # Energy is 32-bit across registers 5 & 6
            energy_raw = (registers[6] << 16) | registers[5]  # Reg 5,6: Energy (32-bit)
            energy = energy_raw                               # Already in Wh

            # Frequency in register 7
            frequency = registers[7] / 10.0                                  # Reg 7: Frequency
            
            # Power factor in register 8
            power_factor_raw = registers[8] / 100.0                          # Reg 8: Power Factor
            
            # Alarm status in register 9 (optional)
            # alarm_status = registers[9]                                      # Reg 9: Alarm

            # Clamp PF to [0.00, 1.00] and set to 0.00 if current is zero
            if current == 0.0 or power == 0:
                power_factor = 0.00
            else:
                power_factor = min(max(power_factor_raw, 0.0), 1.0)

            return {
                'voltage': voltage,
                'current': current,
                'power': power,
                'energy': energy,
                'frequency': frequency, 
                'power_factor': power_factor,
                'timestamp': utime.time()
            }
            
        except Exception as e:
            print(f"Parse error from 0x{address:02X}: {e}")
            return None
    
    def read_tenant_a(self):
        """Read data from Tenant A PZEM-004T-100A"""
        try:
            self.send_command(self.uart_a, self.address_a)
            data = self.read_response(self.uart_a, self.address_a)
            
            if data:
                # Update energy accumulation
                current_time = utime.time()
                if self.last_reading_a > 0:
                    time_diff = current_time - self.last_reading_a
                    # Cap time_diff to avoid large jumps from missed readings
                    if 0 < time_diff <= 10:
                        energy_increment = (data['power'] * time_diff) / 3600 / 1000  # Convert to kWh
                        self.energy_a += energy_increment
                        self.daily_energy_a += energy_increment
                
                self.last_reading_a = current_time
                
                # Add accumulated energy to response
                data['energy'] = self.energy_a
                data['daily_energy'] = self.daily_energy_a
                data['daily_cost'] = self.daily_energy_a * ENERGY_RATE_GHS
                
                return data
            else:
                # Return zeros if no data
                return {
                    'voltage': 0, 'current': 0, 'power': 0, 'energy': self.energy_a,
                    'frequency': 0, 'power_factor': 0, 'timestamp': utime.time(),
                    'daily_energy': self.daily_energy_a, 
                    'daily_cost': self.daily_energy_a * ENERGY_RATE_GHS
                }
        except Exception as e:
            print(f"Tenant A read error: {e}")
            return {
                'voltage': 0, 'current': 0, 'power': 0, 'energy': self.energy_a,
                'frequency': 0, 'power_factor': 0, 'timestamp': utime.time(),
                'daily_energy': self.daily_energy_a,
                'daily_cost': self.daily_energy_a * ENERGY_RATE_GHS
            }
    
    def read_tenant_b(self):
        """Read data from Tenant B PZEM-004T-100A"""
        try:
            self.send_command(self.uart_b, self.address_b)
            data = self.read_response(self.uart_b, self.address_b)
            
            if data:
                # Update energy accumulation
                current_time = utime.time()
                if self.last_reading_b > 0:
                    time_diff = current_time - self.last_reading_b
                    # Cap time_diff to avoid large jumps from missed readings
                    if 0 < time_diff <= 10:
                        energy_increment = (data['power'] * time_diff) / 3600 / 1000  # Convert to kWh
                        self.energy_b += energy_increment
                        self.daily_energy_b += energy_increment
                
                self.last_reading_b = current_time
                
                # Add accumulated energy to response
                data['energy'] = self.energy_b
                data['daily_energy'] = self.daily_energy_b
                data['daily_cost'] = self.daily_energy_b * ENERGY_RATE_GHS
                
                return data
            else:
                # Return zeros if no data
                return {
                    'voltage': 0, 'current': 0, 'power': 0, 'energy': self.energy_b,
                    'frequency': 0, 'power_factor': 0, 'timestamp': utime.time(),
                    'daily_energy': self.daily_energy_b,
                    'daily_cost': self.daily_energy_b * ENERGY_RATE_GHS
                }
        except Exception as e:
            print(f"Tenant B read error: {e}")
            return {
                'voltage': 0, 'current': 0, 'power': 0, 'energy': self.energy_b,
                'frequency': 0, 'power_factor': 0, 'timestamp': utime.time(),
                'daily_energy': self.daily_energy_b,
                'daily_cost': self.daily_energy_b * ENERGY_RATE_GHS
            }
    
    def reset_daily_counters(self):
        """Reset daily energy counters"""
        self.daily_energy_a = 0.0
        self.daily_energy_b = 0.0
        print("Daily energy counters reset")
    
    def set_address(self, uart, old_address, new_address):
        """Set new Modbus address for PZEM-004T-100A module"""
        # This is useful if you need to change module addresses
        # Command: [Old Addr][0x06][0x00][0x02][New Addr][0x00][CRC]
        command = bytearray([
            old_address,
            0x06,  # Write Single Register
            0x00, 0x02,  # Register 2 (address register)
            (new_address >> 8) & 0xFF,
            new_address & 0xFF
        ])
        
        crc = self.crc16_modbus(command)
        command.append(crc & 0xFF)
        command.append((crc >> 8) & 0xFF)
        
        uart.write(bytes(command))
        utime.sleep_ms(200)
        
        # Read response
        if uart.any():
            response = uart.read()
            if len(response) >= 8 and response[0] == old_address and response[1] == 0x06:
                print(f"Successfully changed address from 0x{old_address:02X} to 0x{new_address:02X}")
                return True
        
        print(f"Failed to change address from 0x{old_address:02X} to 0x{new_address:02X}")
        return False
    
    def close(self):
        """Close UART connections"""
        try:
            self.uart_a.deinit()
            self.uart_b.deinit()
        except:
            pass