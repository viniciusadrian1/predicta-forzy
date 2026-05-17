"""Servidor/simulador OPC-UA do motor industrial MTR-001.

Publica 6 variaveis de sensor + a TAG do ativo sob o namespace ``ns=2`` e
expoe nodes de controle gravaveis para ajuste de carga e injecao de falhas.

Endpoint: ``opc.tcp://0.0.0.0:4840/forzy/server/``
"""

from __future__ import annotations

import asyncio
import logging
import os

from asyncua import Server, ua
from fault_injection import FaultInjector, FaultMode
from models import MotorModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("forzy.opcua.simulator")

OPCUA_HOST = os.getenv("OPCUA_HOST", "0.0.0.0")
OPCUA_PORT = int(os.getenv("OPCUA_PORT", "4840"))
NAMESPACE_URI = os.getenv("OPCUA_NAMESPACE_URI", "http://forzy.promon/opcua/")
ASSET_TAG = os.getenv("ASSET_TAG", "MTR-001")
STEP_INTERVAL_S = float(os.getenv("OPCUA_STEP_INTERVAL_S", "1.0"))

SENSOR_NODES = (
    "Tensao",
    "Corrente",
    "Temperatura",
    "Rotacao",
    "Vibracao_Velocidade_RMS",
    "Vibracao_Aceleracao_RMS",
)


async def build_server() -> tuple[Server, dict]:
    """Inicializa o servidor OPC-UA e o address space do motor."""
    server = Server()
    await server.init()
    endpoint = f"opc.tcp://{OPCUA_HOST}:{OPCUA_PORT}/forzy/server/"
    server.set_endpoint(endpoint)
    server.set_server_name("Forzy Digital Twin - OPC-UA Simulator")
    # Simulador local: aceita conexoes anonimas sem seguranca.
    server.set_security_policy([ua.SecurityPolicyType.NoSecurity])

    idx = await server.register_namespace(NAMESPACE_URI)
    logger.info("Namespace '%s' registrado como ns=%d", NAMESPACE_URI, idx)

    objects = server.nodes.objects
    forzy = await objects.add_object(idx, "Forzy")
    motor_root = await forzy.add_object(idx, "Motor")
    motor = await motor_root.add_object(idx, ASSET_TAG)

    nodes: dict = {}
    nodes["TAG"] = await motor.add_variable(idx, "TAG", ASSET_TAG)
    nodes["Tensao"] = await motor.add_variable(idx, "Tensao", 220.0)
    nodes["Corrente"] = await motor.add_variable(idx, "Corrente", 0.0)
    nodes["Temperatura"] = await motor.add_variable(idx, "Temperatura", 25.0)
    nodes["Rotacao"] = await motor.add_variable(idx, "Rotacao", 0.0)
    nodes["Vibracao_Velocidade_RMS"] = await motor.add_variable(
        idx, "Vibracao_Velocidade_RMS", 0.0
    )
    nodes["Vibracao_Aceleracao_RMS"] = await motor.add_variable(
        idx, "Vibracao_Aceleracao_RMS", 0.0
    )

    # Nodes de controle - gravaveis pelo cliente / operador.
    control = await motor.add_object(idx, "Control")
    nodes["LoadSetpoint"] = await control.add_variable(idx, "LoadSetpoint", 0.75)
    nodes["FaultMode"] = await control.add_variable(
        idx, "FaultMode", FaultMode.NONE.value
    )
    nodes["FaultSeverity"] = await control.add_variable(idx, "FaultSeverity", 0.0)
    nodes["BearingWear"] = await control.add_variable(idx, "BearingWear", 0.0)
    for key in ("LoadSetpoint", "FaultMode", "FaultSeverity"):
        await nodes[key].set_writable()

    logger.info("Address space do ativo %s:", ASSET_TAG)
    for name in SENSOR_NODES:
        logger.info("  %-26s -> %s", name, nodes[name].nodeid.to_string())

    return server, nodes


async def run() -> None:
    """Loop principal: avanca o modelo e publica os valores a cada passo."""
    server, nodes = await build_server()
    model = MotorModel()
    injector = FaultInjector()

    async with server:
        logger.info(
            "Simulador OPC-UA ativo em opc.tcp://%s:%d/forzy/server/",
            OPCUA_HOST,
            OPCUA_PORT,
        )
        while True:
            load_setpoint = await nodes["LoadSetpoint"].read_value()
            fault_raw = await nodes["FaultMode"].read_value()
            severity = await nodes["FaultSeverity"].read_value()

            try:
                fault_mode = FaultMode(str(fault_raw).strip().upper())
            except ValueError:
                fault_mode = FaultMode.NONE
            injector.configure(fault_mode, float(severity))

            perturbation = injector.update(STEP_INTERVAL_S)
            reading = model.step(STEP_INTERVAL_S, float(load_setpoint), perturbation)

            await nodes["Tensao"].write_value(reading.voltage_v)
            await nodes["Corrente"].write_value(reading.current_a)
            await nodes["Temperatura"].write_value(reading.temperature_c)
            await nodes["Rotacao"].write_value(reading.rotation_rpm)
            await nodes["Vibracao_Velocidade_RMS"].write_value(
                reading.vibration_velocity_rms
            )
            await nodes["Vibracao_Aceleracao_RMS"].write_value(
                reading.vibration_acceleration_rms
            )
            await nodes["BearingWear"].write_value(round(injector.bearing_wear, 5))

            await asyncio.sleep(STEP_INTERVAL_S)


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Simulador interrompido pelo usuario.")
