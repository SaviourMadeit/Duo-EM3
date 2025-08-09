# =============================================================================
# DUAL-TENANT ENERGY MONITORING SYSTEM - ENHANCED PZEM TEST APPLICATION
# =============================================================================
# File: main.py (Optimized Version)
# Description: Robust and optimized application loop for testing PZEM handler
# Hardware: Raspberry Pi Pico WH + PZEM-004T-100A
# Improvements: Enhanced error handling, data validation, performance optimization
# =============================================================================

import machine
import utime
import gc
import os
from config import *
from pzem_handler import PZEMHandler

class PZEMTestMonitor:
    def __init__(self):
        print("=" * 60)
        print("ENHANCED PZEM-004T-100A Test Monitor Starting...")
        print("=" * 60)
        
        # Configuration validation and display
        if not self._validate_config():
            self.running = False
            return
        
        # Core monitoring variables
        self.running = True
        self.pzem = None
        
        # Timing and scheduling
        self.last_reading = 0
        self.last_stats_print = 0
        self.last_gc_run = 0
        self.startup_time = utime.time()
        
        # Statistics and counters
        self.read_count = 0
        self.stats = {
            'a': {'success': 0, 'error': 0, 'timeout': 0, 'invalid': 0},
            'b': {'success': 0, 'error': 0, 'timeout': 0, 'invalid': 0}
        }
        
        # Data caching and validation
        self.last_valid_data = {'a': None, 'b': None}
        self.consecutive_errors = {'a': 0, 'b': 0}
        self.max_consecutive_errors = 10
        
        # Daily reset tracking
        self.last_daily_reset = 0
        self.test_mode = False  # Set to True for testing frequent resets
        
        # Performance monitoring
        self.timing_stats = {
            'read_a_times': [],
            'read_b_times': [],
            'total_cycle_times': []
        }
        
        # Initialize PZEM handler with retry logic
        self._initialize_pzem()

    def _should_reset_daily_counters(self):
        """Check if daily counters should be reset (at midnight)"""
        current_time = utime.time()
        
        # Get current time structure
        time_struct = utime.localtime(current_time)
        current_hour = time_struct[3]
        current_minute = time_struct[4]
        
        # Check if it's past midnight and we haven't reset today
        if current_hour == 0 and current_minute < 5:  # Reset window: 00:00-00:05
            # Calculate seconds since start of today
            seconds_today = current_hour * 3600 + current_minute * 60 + time_struct[5]
            
            # Only reset if we haven't reset in the last 6 hours (prevents multiple resets)
            if current_time - self.last_daily_reset > 6 * 3600:
                return True
        
        return False

    def _validate_config(self):
        """Validate configuration parameters"""
        required_params = [
            'UART_BAUDRATE', 'SENSOR_READ_INTERVAL', 'ENERGY_RATE_GHS',
            'PZEM_A_TX_PIN', 'PZEM_A_RX_PIN', 'PZEM_B_TX_PIN', 'PZEM_B_RX_PIN'
        ]
        
        try:
            for param in required_params:
                if not hasattr(__import__('config'), param):
                    raise NameError(f"Missing required config parameter: {param}")
            
            # Print validated configuration
            print(f"UART Baudrate: {UART_BAUDRATE}")
            print(f"Sensor read interval: {SENSOR_READ_INTERVAL}s")
            print(f"Energy rate: {ENERGY_RATE_GHS} GHS/kWh")
            print(f"PZEM A pins - TX: {PZEM_A_TX_PIN}, RX: {PZEM_A_RX_PIN}")
            print(f"PZEM B pins - TX: {PZEM_B_TX_PIN}, RX: {PZEM_B_RX_PIN}")
            
            # Validate pin assignments
            if PZEM_A_TX_PIN == PZEM_B_TX_PIN or PZEM_A_RX_PIN == PZEM_B_RX_PIN:
                print("WARNING: Pin conflict detected between PZEM A and B")
                return False
            
            return True
            
        except (NameError, ImportError) as e:
            print(f"Configuration error: {e}")
            print("Please check your config.py file")
            return False

    def _initialize_pzem(self):
        """Initialize PZEM handler with retry logic"""
        max_retries = 3
        retry_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                print(f"Initializing PZEM handler (attempt {attempt + 1}/{max_retries})...")
                self.pzem = PZEMHandler()
                
                # Test connectivity
                if self._test_connectivity():
                    print("PZEM Handler initialized successfully")
                    print("Module A address: 0x01, Module B address: 0x02")
                    return
                else:
                    print("PZEM connectivity test failed")
                    if self.pzem:
                        self.pzem.close()
                    self.pzem = None
                    
            except Exception as e:
                print(f"PZEM initialization attempt {attempt + 1} failed: {e}")
                if self.pzem:
                    try:
                        self.pzem.close()
                    except:
                        pass
                self.pzem = None
            
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                utime.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
        
        print("Failed to initialize PZEM handler after all retries")
        self.running = False

    def _test_connectivity(self):
        """Test basic connectivity to both PZEM modules"""
        if not self.pzem:
            return False
        
        try:
            # Quick connectivity test
            data_a = self.pzem.read_tenant_a()
            utime.sleep_ms(200)
            data_b = self.pzem.read_tenant_b()
            
            # Check if we got any response (even if all zeros)
            return data_a is not None and data_b is not None
            
        except Exception as e:
            print(f"Connectivity test error: {e}")
            return False

    def _validate_data(self, data, tenant_id):
        """Enhanced data validation with sanity checks"""
        if not data or not isinstance(data, dict):
            return False, "No data or invalid format"
        
        required_fields = ['voltage', 'current', 'power', 'energy', 'frequency', 'power_factor']
        for field in required_fields:
            if field not in data:
                return False, f"Missing field: {field}"
        
        # Sanity checks
        voltage = data['voltage']
        current = data['current']
        power = data['power']
        frequency = data['frequency']
        power_factor = data['power_factor']
        
        # Voltage range check (typical mains: 200-250V)
        if voltage > 0 and (voltage < 180 or voltage > 280):
            return False, f"Voltage out of range: {voltage}V"
        
        # Current sanity check (PZEM-004T max: 100A)
        if current < 0 or current > 100:
            return False, f"Current out of range: {current}A"
        
        # Power sanity check
        if power < 0 or power > 25000:  # 25kW max for 100A@250V
            return False, f"Power out of range: {power}W"
        
        # Frequency check (typical: 45-65Hz)
        if frequency > 0 and (frequency < 45 or frequency > 65):
            return False, f"Frequency out of range: {frequency}Hz"
        
        # Power factor check
        if power_factor < 0 or power_factor > 1:
            return False, f"Power factor out of range: {power_factor}"
        
        # Cross-validation: P ≈ V × I × PF (allow 10% tolerance)
        if voltage > 10 and current > 0.01:  # Only check if significant load
            calculated_power = voltage * current * power_factor
            power_diff = abs(power - calculated_power)
            if power_diff > calculated_power * 0.1:
                return False, f"Power validation failed: P={power}W, V×I×PF={calculated_power:.1f}W"
        
        return True, "Valid"

    def _format_reading(self, data, tenant_name, is_valid=True, error_msg=""):
        """Enhanced formatting with validation status"""
        if not data:
            return f"{tenant_name}: No data - {error_msg}"
        
        status_indicator = "✓" if is_valid else "⚠"
        
        # Check if we have any real load
        has_load = any(v > 0.01 for v in [data.get('current', 0), data.get('power', 0)])
        
        if has_load:
            return (f"{tenant_name} {status_indicator}: "
                   f"V={data['voltage']:.1f}V, "
                   f"I={data['current']:.3f}A, "
                   f"P={data['power']:.1f}W, "
                   f"E={data['energy']:.4f}kWh, "
                   f"F={data['frequency']:.1f}Hz, "
                   f"PF={data['power_factor']:.2f}, "
                   f"Daily={data.get('daily_energy', 0):.4f}kWh "
                   f"(GHS {data.get('daily_cost', 0):.4f})")
        else:
            return (f"{tenant_name} {status_indicator}: No load - "
                   f"Daily={data.get('daily_energy', 0):.4f}kWh "
                   f"(GHS {data.get('daily_cost', 0):.4f})")

    def _update_stats(self, tenant, result_type):
        """Update statistics with new result"""
        if tenant in self.stats and result_type in self.stats[tenant]:
            self.stats[tenant][result_type] += 1

    def _should_restart_handler(self, tenant):
        """Determine if PZEM handler should be restarted due to errors"""
        return self.consecutive_errors[tenant] >= self.max_consecutive_errors

    def _restart_pzem_handler(self):
        """Restart PZEM handler after too many errors"""
        print("Too many consecutive errors - restarting PZEM handler...")
        
        if self.pzem:
            try:
                self.pzem.close()
            except:
                pass
        
        # Reset error counters
        self.consecutive_errors = {'a': 0, 'b': 0}
        
        # Reinitialize
        self._initialize_pzem()

    def _read_tenant_data(self, tenant_id):
        """Enhanced tenant data reading with timing and error handling"""
        start_time = utime.ticks_ms()
        tenant = 'a' if tenant_id == 'A' else 'b'
        
        try:
            # Read data based on tenant
            if tenant_id == 'A':
                data = self.pzem.read_tenant_a()
            else:
                data = self.pzem.read_tenant_b()
            
            read_time = utime.ticks_diff(utime.ticks_ms(), start_time)
            
            if data is None:
                self._update_stats(tenant, 'timeout')
                self.consecutive_errors[tenant] += 1
                return None, f"Communication timeout ({read_time}ms)"
            
            # Validate data
            is_valid, validation_msg = self._validate_data(data, tenant_id)
            
            if is_valid:
                self._update_stats(tenant, 'success')
                self.consecutive_errors[tenant] = 0  # Reset error counter
                self.last_valid_data[tenant] = data
                
                # Store timing data (keep last 10 readings)
                timing_key = f'read_{tenant}_times'
                self.timing_stats[timing_key].append(read_time)
                if len(self.timing_stats[timing_key]) > 10:
                    self.timing_stats[timing_key].pop(0)
                
                return data, f"OK ({read_time}ms)"
            else:
                self._update_stats(tenant, 'invalid')
                self.consecutive_errors[tenant] += 1
                return data, f"Invalid data: {validation_msg} ({read_time}ms)"
                
        except Exception as e:
            read_time = utime.ticks_diff(utime.ticks_ms(), start_time)
            self._update_stats(tenant, 'error')
            self.consecutive_errors[tenant] += 1
            return None, f"Error: {e} ({read_time}ms)"

    def _print_enhanced_statistics(self):
        """Print comprehensive statistics"""
        uptime = utime.time() - self.startup_time
        print(f"\n--- Statistics (Uptime: {uptime}s) ---")
        
        for tenant_name, tenant_key in [("Tenant A", "a"), ("Tenant B", "b")]:
            stats = self.stats[tenant_key]
            total = sum(stats.values())
            
            if total > 0:
                success_rate = (stats['success'] / total) * 100
                print(f"{tenant_name}: {success_rate:.1f}% success "
                      f"({stats['success']}/{total}) - "
                      f"Errors: {stats['error']}, "
                      f"Timeouts: {stats['timeout']}, "
                      f"Invalid: {stats['invalid']}")
                
                # Print average read time
                timing_key = f'read_{tenant_key}_times'
                if self.timing_stats[timing_key]:
                    avg_time = sum(self.timing_stats[timing_key]) / len(self.timing_stats[timing_key])
                    print(f"{tenant_name} avg read time: {avg_time:.1f}ms")
            else:
                print(f"{tenant_name}: No readings yet")
        
        # Memory and performance info
        print(f"Memory free: {gc.mem_free()} bytes")
        if self.timing_stats['total_cycle_times']:
            avg_cycle = sum(self.timing_stats['total_cycle_times']) / len(self.timing_stats['total_cycle_times'])
            print(f"Average cycle time: {avg_cycle:.1f}ms")

    def run(self):
        """Enhanced main monitoring loop"""
        if not self.running or not self.pzem:
            print("Cannot start - initialization failed")
            return
            
        print("\nStarting enhanced PZEM monitoring loop...")
        print("Features: Data validation, performance monitoring, auto-recovery")
        print("Press Ctrl+C to stop")
        print("-" * 60)
        
        try:
            while self.running:
                cycle_start = utime.ticks_ms()
                current_time = utime.time()
                
                # Check if it's time for readings
                if current_time - self.last_reading >= SENSOR_READ_INTERVAL:
                    self.read_count += 1
                    print(f"\n--- Reading #{self.read_count} at {current_time} ---")
                    
                    # Check if we need to restart handler due to errors
                    if (self._should_restart_handler('a') or self._should_restart_handler('b')):
                        self._restart_pzem_handler()
                        if not self.running:  # If restart failed
                            break
                    
                    # Read Tenant A
                    data_a, status_a = self._read_tenant_data('A')
                    is_valid_a = "OK" in status_a
                    print(self._format_reading(data_a, "Tenant A", is_valid_a, status_a))
                    
                    # Inter-reading delay
                    utime.sleep_ms(200)
                    
                    # Read Tenant B
                    data_b, status_b = self._read_tenant_data('B')
                    is_valid_b = "OK" in status_b
                    print(self._format_reading(data_b, "Tenant B", is_valid_b, status_b))
                    
                    self.last_reading = current_time
                    
                    # Store cycle timing
                    cycle_time = utime.ticks_diff(utime.ticks_ms(), cycle_start)
                    self.timing_stats['total_cycle_times'].append(cycle_time)
                    if len(self.timing_stats['total_cycle_times']) > 10:
                        self.timing_stats['total_cycle_times'].pop(0)
                
                # Periodic maintenance
                if current_time - self.last_stats_print >= 30:  # Every 30 seconds
                    self._print_enhanced_statistics()
                    self.last_stats_print = current_time
                
                # Garbage collection
                if current_time - self.last_gc_run >= 60:  # Every minute
                    gc.collect()
                    self.last_gc_run = current_time
                
                # Daily counter reset - check for midnight rollover
                if self._should_reset_daily_counters():
                    print("Resetting daily counters (midnight rollover)")
                    try:
                        self.pzem.reset_daily_counters()
                        self.last_daily_reset = current_time
                    except Exception as e:
                        print(f"Error resetting daily counters: {e}")
                
                # Test mode reset (optional - every 100 readings for testing)
                if hasattr(self, 'test_mode') and self.test_mode and self.read_count % 100 == 0:
                    print("Resetting daily counters (test mode)")
                    try:
                        self.pzem.reset_daily_counters()
                    except Exception as e:
                        print(f"Error resetting daily counters: {e}")
                
                # Adaptive sleep based on performance
                sleep_time = max(50, 200 - cycle_time) if cycle_time < 200 else 50
                utime.sleep_ms(sleep_time)
                
        except KeyboardInterrupt:
            print("\n\nMonitoring stopped by user (Ctrl+C)")
        except Exception as e:
            print(f"\nUnexpected error in main loop: {e}")
            import sys
            sys.print_exception(e)
        finally:
            self.cleanup()

    def cleanup(self):
        """Enhanced cleanup with comprehensive summary"""
        print("\n" + "=" * 60)
        print("ENHANCED CLEANUP SUMMARY")
        print("=" * 60)
        
        uptime = utime.time() - self.startup_time
        print(f"Total uptime: {uptime} seconds")
        print(f"Total readings attempted: {self.read_count}")
        
        # Detailed statistics
        for tenant_name, tenant_key in [("Tenant A", "a"), ("Tenant B", "b")]:
            stats = self.stats[tenant_key]
            total = sum(stats.values())
            if total > 0:
                success_rate = (stats['success'] / total) * 100
                print(f"{tenant_name}: {success_rate:.1f}% success rate")
                print(f"  - Successful readings: {stats['success']}")
                print(f"  - Communication errors: {stats['error']}")
                print(f"  - Timeouts: {stats['timeout']}")
                print(f"  - Invalid data: {stats['invalid']}")
        
        # Last valid readings
        for tenant_name, tenant_key in [("Tenant A", "a"), ("Tenant B", "b")]:
            last_data = self.last_valid_data[tenant_key]
            if last_data:
                print(f"Last valid {tenant_name}: {self._format_reading(last_data, tenant_name)}")
        
        # Energy totals
        if self.pzem:
            try:
                print(f"Total accumulated energy A: {self.pzem.energy_a:.6f} kWh")
                print(f"Total accumulated energy B: {self.pzem.energy_b:.6f} kWh")
                print(f"Daily energy A: {self.pzem.daily_energy_a:.6f} kWh (GHS {self.pzem.daily_energy_a * ENERGY_RATE_GHS:.4f})")
                print(f"Daily energy B: {self.pzem.daily_energy_b:.6f} kWh (GHS {self.pzem.daily_energy_b * ENERGY_RATE_GHS:.4f})")
                
                self.pzem.close()
                print("PZEM handler closed successfully")
            except Exception as e:
                print(f"Error during PZEM cleanup: {e}")
        
        print("Enhanced cleanup complete.")

# Enhanced utility functions
def test_single_reading():
    """Enhanced single reading test with validation"""
    print("Testing single PZEM readings with validation...")
    monitor = PZEMTestMonitor()
    
    if not monitor.pzem:
        print("Failed to initialize PZEM handler")
        return
    
    try:
        print("Reading Tenant A...")
        data_a, status_a = monitor._read_tenant_data('A')
        print(f"A: {status_a}")
        if data_a:
            print(f"  Data: {monitor._format_reading(data_a, 'A')}")
        
        utime.sleep_ms(500)
        
        print("Reading Tenant B...")
        data_b, status_b = monitor._read_tenant_data('B')
        print(f"B: {status_b}")
        if data_b:
            print(f"  Data: {monitor._format_reading(data_b, 'B')}")
        
    except Exception as e:
        print(f"Test failed: {e}")
    finally:
        monitor.cleanup()

def performance_test(duration=30):
    """Run performance test for specified duration"""
    print(f"Running performance test for {duration} seconds...")
    monitor = PZEMTestMonitor()
    
    if not monitor.pzem:
        print("Failed to initialize PZEM handler")
        return
    
    start_time = utime.time()
    readings = 0
    
    try:
        while utime.time() - start_time < duration:
            data_a, _ = monitor._read_tenant_data('A')
            utime.sleep_ms(100)
            data_b, _ = monitor._read_tenant_data('B')
            utime.sleep_ms(100)
            readings += 2
        
        elapsed = utime.time() - start_time
        rate = readings / elapsed
        print(f"Performance: {rate:.2f} readings/second over {elapsed:.1f} seconds")
        monitor._print_enhanced_statistics()
        
    except Exception as e:
        print(f"Performance test failed: {e}")
    finally:
        monitor.cleanup()

def main():
    """Enhanced main entry point with better error handling"""
    try:
        # System info
        print(f"Free memory at startup: {gc.mem_free()} bytes")
        
        # Check if we have enough memory
        if gc.mem_free() < 10000:  # 10KB minimum
            print("WARNING: Low memory detected. Running garbage collection...")
            gc.collect()
            if gc.mem_free() < 5000:
                print("CRITICAL: Insufficient memory. System may be unstable.")
        
        monitor = PZEMTestMonitor()
        monitor.run()
        
    except MemoryError:
        print("FATAL: Out of memory")
        gc.collect()
        machine.reset()
    except Exception as e:
        print(f"Fatal error in main: {e}")
        import sys
        sys.print_exception(e)
        print("System will restart in 10 seconds...")
        utime.sleep(10)
        machine.reset()

if __name__ == "__main__":
    main()