# =============================================================================
# CONFIGURATION FILE
# =============================================================================
# File: config.py
# Description: System configuration and constants

# Hardware Pin Definitions
PZEM_A_TX_PIN = 0      # UART0 TX for Tenant A PZEM
PZEM_A_RX_PIN = 1      # UART0 RX for Tenant A PZEM
PZEM_B_TX_PIN = 4      # UART1 TX for Tenant B PZEM  
PZEM_B_RX_PIN = 5      # UART1 RX for Tenant B PZEM

GSM_TX_PIN = 16        # Software UART TX for SIM800L
GSM_RX_PIN = 17        # Software UART RX for SIM800L

I2C_SDA_PIN = 8        # I2C SDA for LCD and RTC
I2C_SCL_PIN = 9        # I2C SCL for LCD and RTC

BUZZER_PIN = 18        # PWM pin for buzzer
LED_GREEN_PIN = 19     # Green LED (Normal)
LED_RED_PIN = 20       # Red LED (Alert)
LED_BLUE_PIN = 21      # Blue LED (Communication)
LED_SYSTEM_PIN = 22    # System status LED

# System Constants
ENERGY_RATE_GHS = 1.824        # Ghana Cedis per kWh
DAILY_ENERGY_THRESHOLD = 10.0   # kWh threshold for alerts
DAILY_COST_THRESHOLD = 20.0     # GHS threshold for alerts
BUZZER_FREQUENCY = 2000         # Alert buzzer frequency in Hz

# Timing Intervals (seconds)
SENSOR_READ_INTERVAL = 1        # Read sensors every 1 second
DISPLAY_UPDATE_INTERVAL = 2     # Update display every 2 seconds  
DATA_LOG_INTERVAL = 60          # Log data every 60 seconds
SMS_CHECK_INTERVAL = 300        # Check for SMS alerts every 5 minutes
WATCHDOG_TIMEOUT = 30           # Watchdog timeout in seconds

# I2C Addresses
LCD_I2C_ADDR = 0x27         # LCD I2C address
RTC_I2C_ADDR = 0x68         # DS3231 RTC I2C address

# Communication Settings
UART_BAUDRATE = 9600           # PZEM and GSM baud rate
SMS_RECIPIENTS = ["+233XXXXXXXXX", "+233YYYYYYYYY"]  # SMS recipient numbers

# ThingSpeak Settings
THINGSPEAK_API_KEY = "YOUR_THINGSPEAK_WRITE_API_KEY"
THINGSPEAK_CHANNEL_ID = "YOUR_CHANNEL_ID"

# WiFi Settings  
WIFI_SSID = "YOUR_WIFI_SSID"
WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"

# Web Server Settings
WEB_SERVER_PORT = 80
API_UPDATE_INTERVAL = 300      # Update web API every 5 minutes
