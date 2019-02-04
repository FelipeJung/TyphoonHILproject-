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

name = "boost_current_control_connected_to_bus"
dirpath = os.path.dirname(os.path.abspath(__file__))
schfilename = os.path.join(dirpath,name+".tse")
modelfilename = os.path.join(dirpath, name + ' Target files', name + '.cpd')

@pytest.fixture(scope="session")
def setup_to_steady_state():
    model.load(schfilename)
    model.compile()
    
    hil.load_model(modelfilename, vhil_device = True)
    
    hil.set_scada_input_value("Enable", 0)
    hil.set_scada_input_value("Reset", 1.0)
    hil.set_source_constant_value("Input", 240.0)
    hil.set_source_constant_value("Bus", 380.0)
    hil.set_scada_input_value("Pout_reference", 0.0)
    hil.start_simulation()
    

    hil.set_scada_input_value("Enable", 1)
    wait_until("Ia1", region = "at", value = (-20.0, 20.0), interval = 1, timeout = 10)
    hil.set_scada_input_value("Reset", 0)
    yield
    
    hil.set_source_constant_value("Input", 240.0)
    hil.set_scada_input_value("Pout_reference", 0.0)
    hil.set_scada_input_value("Enable", 0)
    hil.stop_simulation()

def reset(setpoint):
    hil.set_scada_input_value("Reset", 1.0)
    hil.set_scada_input_value("Pout_reference", setpoint)
    wait_until("Pout", region = "at", value = (setpoint*0.80, setpoint*1.20), interval = 1, timeout = 10)
    hil.set_scada_input_value("Reset", 0)
    return
    
# define setpoint as the power wanted to be injected into or from the bus
@pytest.mark.parametrize("setpoint", [-10000.0, -30000.0, 10000.0, 30000.0])
def test_reference_step(setup_to_steady_state, setpoint):
    hil.set_scada_input_value("reference_is_ramp", 0)
    reset(100.0)
    start_capture(duration=0.3, rate=100000, signals=["Pout", "Ia1", "Vout"])
    hil.wait_msec(100)
    hil.set_scada_input_value("Pout_reference", setpoint)
    
    capture = get_capture_results(wait_capture=True)
    assert_is_step(capture["Pout"], from_value=around(100, tol = 15.0),
                   to_value = around(setpoint, tol_p = 0.6), at_t = around(0.11, tol = 0.01))
    
    hil.set_scada_input_value("Pout_reference", 100.0)
    
def test_current_ripple(setup_to_steady_state):
    hil.set_scada_input_value("reference_is_ramp", 0)
    setpoint = 30000.0
    reset(setpoint)
    ia_n = 30000/240
    start_capture(duration=0.1, rate=50000, signals=["Ia1"])

    capture = get_capture_results(wait_capture=True)
    assert_is_constant(capture["Ia1"], at_value=around(ia_n, tol_p=0.2))
    
    hil.set_scada_input_value("Pout_reference", 100.0)
    
def test_overcurrent(setup_to_steady_state):
    hil.set_scada_input_value("reference_is_ramp", 0)
    initial_state = 100.0
    reset(initial_state)
    start_capture(duration = 0.3, rate = 1e5, signals = ["Ia1"])
    hil.wait_msec(50)
    hil.set_scada_input_value("Pout_reference", 30000.0)
    hil.wait_msec(200)
    hil.set_scada_input_value("Pout_reference", 50000.0)
    capture = get_capture_results(wait_capture=True)
    
    start_capture(duration = 0.1, rate = 1e4, signals = ["Ia1"])
    capture = get_capture_results(wait_capture=True)
    assert_is_constant(capture["Ia1"], at_value=around(0,tol=1))
    
    reset(initial_state)
    
def test_overvoltage(setup_to_steady_state):
    hil.set_scada_input_value("reference_is_ramp", 0)
    initial_state = 100.0
    setpoint = 30000.0
    #reset(initial_state)
    reset(setpoint)
    start_capture(duration = 0.5, rate = 100000, signals = ["Battery_voltage", "Vout", "Ia1"])
    hil.set_source_constant_value("Input", value=300, ramp_time=0.2, ramp_type='lin')
    capture = get_capture_results(wait_capture = True)
    
    start_capture(duration = 0.1, rate = 1e4, signals = ["Ia1"])
    capture = get_capture_results(wait_capture=True)
    assert_is_constant(capture["Ia1"], at_value=around(0,tol=1))
    hil.set_source_constant_value("Input", 240.0)
    reset(initial_state)
    
    

def test_undervoltage(setup_to_steady_state):
    hil.set_scada_input_value("reference_is_ramp", 0)
    initial_state = 100.0
    setpoint = 30000.0
    #reset(initial_state)
    reset(setpoint)
    start_capture(duration = 0.5, rate = 100000, signals = ["Battery_voltage", "Vout", "Ia1"])
    hil.set_source_constant_value("Input", value=180, ramp_time=0.2, ramp_type='lin')
    capture = get_capture_results(wait_capture = True)
    
    start_capture(duration = 0.1, rate = 1e4, signals = ["Ia1"])
    capture = get_capture_results(wait_capture=True)
    assert_is_constant(capture["Ia1"], at_value=around(0,tol=1))
    hil.set_source_constant_value("Input", 240.0)
    reset(initial_state)

    
def test_ramp(setup_to_steady_state):
    hil.set_scada_input_value("reference_is_ramp", 1)
    initial_state = 100.0
    setpoint = 30000.0
    reset(initial_state)
    start_capture(duration=1, rate=100000, signals=["Pout", "Ia1", "Pout_calc"])

    reset(setpoint)
    
    capture = get_capture_results(wait_capture=True)
    ramp_duration = 0.5
    t_ramp_start = find(capture["Pout"], region = "above", 
                        value = 100.0)
    t_ramp_end = t_ramp_start+td(ramp_duration)
    
    assert_is_ramp(capture["Pout"], slope = (setpoint-initial_state)/ramp_duration,
                    tol = 700, during = (t_ramp_start, t_ramp_end))
    
    hil.set_scada_input_value("Pout_reference", 100.0)