import typhoon.api.hil as hil
from typhoon.api.schematic_editor import model
from typhoon.test.capture import *
from typhoon.test.signals import *
from typhoon.test.ranges import *
from typhoon.test.sources import *
import os
import pytest
import logging
from typhoon.types.timedelta import Timedelta as td

name = "boost_current_control_resistive_load"
dirpath = os.path.dirname(os.path.abspath(__file__))
schfilename = os.path.join(dirpath,name+".tse")
modelfilename = os.path.join(dirpath, name + ' Target files', name + '.cpd')

@pytest.fixture(scope="session")
def setup():
    model.load(schfilename)
    model.compile()
    
    hil.load_model(modelfilename, vhil_device = True)
    
    hil.set_scada_input_value("Aciona_carga", 0.0)
    hil.set_scada_input_value("Enable", 0)
    hil.set_scada_input_value("Reset", 1.0)
    hil.start_simulation()
    
    hil.set_source_constant_value("Input", 240.0)
    hil.set_scada_input_value("Voltage_reference", 240.0)
    hil.set_scada_input_value("Enable", 1)
    hil.set_scada_input_value("Reset", 0)
    
    yield
    
    hil.set_source_constant_value("Input", 240.0)
    hil.set_scada_input_value("Voltage_reference", 240.0)
    hil.set_scada_input_value("Enable", 0)
    hil.stop_simulation()

def reset(setpoint):
    hil.set_scada_input_value("Reset", 1.0)
    hil.set_scada_input_value("Voltage_reference", setpoint)
    hil.wait_msec(100)
    hil.set_scada_input_value("Reset", 0)
    return
    
def modo_de_operacao(modo):
    if (modo == "step"):
        hil.set_scada_input_value("ramp", 0)
    if (modo == "ramp"):
        hil.set_scada_input_value("ramp", 1)
    hil.wait_msec(2)
    return
    

@pytest.mark.parametrize("setpoint", [280.0, 320.0, 380.0])
def test_reference_step(setup, setpoint):
    modo_de_operacao("step")
    reset(240.0)
    hil.wait_msec(200)
    start_capture(duration=0.3, rate=100000, signals=["Vout", "Ia1"])
    hil.wait_msec(100)
    hil.set_scada_input_value("Voltage_reference", setpoint)
    
    capture = get_capture_results(wait_capture=True)
    assert_is_step(capture["Vout"], from_value=around(240.0, tol_p = 0.05),
                   to_value = around(setpoint, tol_p = 0.10), at_t = around(0.125, tol = 0.03))
    
    hil.set_scada_input_value("Voltage_reference", 240.0)
    hil.wait_msec(200)
 
def test_voltage_ripple(setup):
    modo_de_operacao("step")
    setpoint = 380.0
    reset(setpoint)
    
    start_capture(duration=0.1, rate=50000, signals=["Vout"])

    capture = get_capture_results(wait_capture=True)
    assert_is_constant(capture["Vout"], at_value=around(setpoint,tol_p=0.02))
    
    hil.set_scada_input_value("Voltage_reference", 240.0)
    
def test_current_ripple(setup):
    modo_de_operacao("step")
    setpoint = 380.0
    reset(setpoint)
    ia_n = 30000/240
    start_capture(duration=0.1, rate=50000, signals=["Ia1"])

    capture = get_capture_results(wait_capture=True)
    assert_is_constant(capture["Ia1"], at_value=around(ia_n, tol_p=0.2))
    
    hil.set_scada_input_value("Voltage_reference", 240.0) 
    
def test_overcurrent(setup):
    modo_de_operacao("step")
    reset(240.0)
    start_capture(duration = 0.3, rate = 1e5, signals = ["Ia1", "Vout"])
    hil.wait_msec(50)
    hil.set_scada_input_value("Voltage_reference", 380.0)
    hil.wait_msec(200)
    hil.set_scada_input_value("Aciona_carga", 1.0)
    capture = get_capture_results(wait_capture=True)
    
    start_capture(duration = 0.1, rate = 1e4, signals = ["Ia1"])
    capture = get_capture_results(wait_capture=True)
    assert_is_constant(capture["Ia1"], at_value=around(0,tol=1))
    
    hil.set_scada_input_value("Aciona_carga", 0.0)
    hil.set_scada_input_value("Voltage_reference", 240.0)


def test_overvoltage(setup):
    modo_de_operacao("ramp")
    setpoint = 380.0
    reset(setpoint)
    start_capture(duration = 0.5, rate = 5000, signals = ["Battery_voltage", "Vout", "Ia1"])
    hil.set_source_constant_value("Input", value=300, ramp_time=0.2, ramp_type='lin')
    capture = get_capture_results(wait_capture = True)
    conversor_ligado = hil.read_digital_signal("Protecao")
    
    assert (conversor_ligado == 0)
    
    hil.set_source_constant_value("Input", 240.0)
    

def test_undervoltage(setup):
    modo_de_operacao("step")
    setpoint = 380.0
    reset(setpoint)
    start_capture(duration = 0.5, rate = 5000, signals = ["Battery_voltage", "Vout", "Ia1"])
    hil.set_source_constant_value("Input", value=180, ramp_time=0.2, ramp_type='lin')
    capture = get_capture_results(wait_capture = True)
    conversor_ligado = hil.read_digital_signal("Protecao")
    
    assert (conversor_ligado == 0)
    hil.set_source_constant_value("Input", 240.0)
    
def test_ramp(setup):
    modo_de_operacao("ramp")
    reset(250.0)
    hil.wait_msec(1000)
    start_capture(duration=1, rate=100000, signals=["Vout", "Ia1", "V_ref_calc"])
    
    hil.set_scada_input_value("Voltage_reference", 380.0)
    
    capture = get_capture_results(wait_capture=True)
    ramp_duration = 0.5
    t_ramp_start = find(capture["Vout"], region = "above", 
                        value = 250.0)
    t_ramp_end = t_ramp_start+td(ramp_duration)
    
    assert_is_ramp(capture["Vout"], slope = (380.0-250.0)/ramp_duration,
                    tol = 10, during = (t_ramp_start, t_ramp_end))
    
    hil.set_scada_input_value("Voltage_reference", 240.0)
    #hil.wait_msec(200)