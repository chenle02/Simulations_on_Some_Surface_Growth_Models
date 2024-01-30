
local dap = require('dap')

dap.adapters.python = {
  type = 'executable';
  command = '/usr/local/bin/python3';  -- Path to the Python interpreter
  args = { '-m', 'debugpy.adapter' };
}

dap.configurations.python = {
  {
    type = 'python';
    request = 'launch';
    name = "pytest";
    program = '/home/lechen/.local/bin/pytest';  -- Path to the pytest executable
    args = {'-s', 'test_save_config.py'};  -- Path to your test file
    pythonPath = function()
      return '/usr/local/bin/python3'  -- Path to the Python interpreter
    end;
  },
}
