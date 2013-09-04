# -*- coding: utf-8 -*-
"""
"""
from visa import Instrument

class YokogawaGS200(Instrument):
    """
    """

    def __init__(self, connection_str):

        super(YokogawaGS200, self).__init__(connection_str)

    def set_voltage(self, set_point):
        """
        """
        self.write(":SOURce:LEVel {}".format(set_point))

    def get_voltage(self):
        """
        """
        return self.ask_for_values(":SOURce:LEVel?")[0]

    def set_function(self, mode):
        """
        """
        if mode == 'VOLT':
            self.write(':SOURce:FUNCtion VOLT')
        elif mode == 'CURR':
            self.write(':SOURce:FUNCtion CURR')
        else:
            print 'Mode unsupported for the YokogawaGS200'