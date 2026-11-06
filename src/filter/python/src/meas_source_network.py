"""
This file is part of Learned Inertial Model Odometry.
Copyright (C) 2023 Giovanni Cioffi <cioffi at ifi dot uzh dot ch>
(Robotics and Perception Group, University of Zurich, Switzerland).
This file is subject to the terms and conditions defined in the file
'LICENSE', which is part of this source code package.
"""

"""
Reference: https://github.com/CathIAS/TLIO/blob/master/src/tracker/meas_source_network.py
"""

import numpy as np
import torch

from learning.network.model_factory import get_model
from filter.python.src.utils.logging import logging


class MeasSourceNetwork:
    def __init__(self, model_path, force_cpu=False, input_dim=6):
        # network
        self.net = get_model(input_dim, 3)

        # load trained network model
        if not torch.cuda.is_available() or force_cpu:
            self.device = torch.device("cpu")
            checkpoint = torch.load(
                model_path, map_location=lambda storage, location: storage, weights_only=False
            )
        else:
            self.device = torch.device("cuda:0")
            checkpoint = torch.load(model_path, weights_only=False)

        self.net.load_state_dict(checkpoint["model_state_dict"])
        self.net.eval().to(self.device)
        logging.info("Model {} loaded to device {}.".format(model_path, self.device))

    def get_displacement_measurement(self, net_t_s, features):
        # features: N x input_dim, see learning/data_management/features.py
        features_t = torch.unsqueeze(
            torch.from_numpy(features.T).float().to(self.device), 0
        )  # 1 x 6 x N

        # get inference
        with torch.no_grad():
            dp_learnt = self.net(features_t)

        # define measurement
        meas = dp_learnt.cpu().detach().numpy()
        meas = meas.reshape((3, 1))
        # ToDo: learn covariance
        meas_cov = np.eye(3)

        return meas, meas_cov

