import smbus2, bme280, time, os, asyncio, json, uuid
from grove.grove_moisture_sensor import GroveMoistureSensor
from grove.grove_light_sensor_v1_2 import GroveLightSensor
from dotenv import load_dotenv
from azure.iot.device.aio import IoTHubDeviceClient, ProvisioningDeviceClient
from azure.iot.device import MethodResponse

# Configuration parameters
light_pin = 0
bme_pin = 1
moisture_pin = 2

bme_address = 0x76

# Create the sensors
bus = smbus2.SMBus(bme_pin)
calibration_params = bme280.load_calibration_params(bus, bme_address)

moisture_sensor = GroveMoistureSensor(moisture_pin)
light_sensor = GroveLightSensor(light_pin)

# Load the IoT Central connection parameters
load_dotenv()
id_scope = os.getenv('ID_SCOPE')
device_id = os.getenv('DEVICE_ID')
primary_key = os.getenv('PRIMARY_KEY')

def getTemperaturePressureHumidity():
    return bme280.sample(bus, bme_address, calibration_params)

def getLight():
    return light_sensor.light

def getMoisture():
    return moisture_sensor.moisture

def getDescriptionForMoisture(moisture):
    if 0 <= moisture and moisture < 300:
        return 'Dry'
    elif 300 <= moisture and moisture < 600:
        return 'Moist'
    else:
        return 'Wet'

def getTelemetryData():
    temp_pressure_humidity = getTemperaturePressureHumidity()
    light = getLight()
    moisture = getMoisture()
    moisture_description = getDescriptionForMoisture(moisture)

    data = {
        "Humidity": round(temp_pressure_humidity.humidity, 2),
        "Pressure": round(temp_pressure_humidity.pressure/10, 2),
        "Temperature": round(temp_pressure_humidity.temperature, 2),
        "Light": round(light, 2),
        "SoilMoisture": round(moisture, 2),
        "MoistureDescription": moisture_description,
        "id": str(uuid.uuid4())
    }

    return json.dumps(data)

async def main():
    # provision the device
    async def register_device():
        provisioning_device_client = ProvisioningDeviceClient.create_from_symmetric_key(
            provisioning_host='global.azure-devices-provisioning.net',
            registration_id=device_id,
            id_scope=id_scope,
            symmetric_key=primary_key,
        )

        return await provisioning_device_client.register()

    results = await asyncio.gather(register_device())
    registration_result = results[0]

    # build the connection string
    conn_str='HostName=' + registration_result.registration_state.assigned_hub + \
                ';DeviceId=' + device_id + \
                ';SharedAccessKey=' + primary_key

    # The client object is used to interact with your Azure IoT Central.
    device_client = IoTHubDeviceClient.create_from_connection_string(conn_str)

    # connect the client.
    print('Connecting')
    await device_client.connect()
    print('Connected')

    # listen for commands
    async def command_listener(device_client):
        global mode
        while True:
            method_request = await device_client.receive_method_request()
            payload = {'result': True, 'data': method_request.name}
            method_response = MethodResponse.create_from_method_request(
                method_request, 200, payload
            )
            await device_client.send_method_response(method_response)

    # async loop that controls the lights
    async def main_loop():
        while True:            
            telemetry = getTelemetryData()
            print(telemetry)

            await device_client.send_message(telemetry)
            await asyncio.sleep(1)

    listeners = asyncio.gather(command_listener(device_client))

    await main_loop()

    # Cancel listening
    listeners.cancel()

    # Finally, disconnect
    await device_client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())











data = getTemperaturePressureHumidity()
print("Temperature:", data.temperature)
print("Pressure:", data.pressure)
print("Humidity:", data.humidity)

print('Light value: {0}'.format(getLight()))

moisture = getMoisture()

print('Moisture value: {0}, {1}'.format(moisture, getDescriptionForMoisture(moisture)))
