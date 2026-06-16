# Ex-IMO
Extended Model Based Learned Inertial Odometry

> **Code will be available soon.**

## Abstract

Inertial odometry is a compelling approach to state estimation for agile quadrotor flight due to its affordability, low weight, and robustness to perceptual degradation. However, relying only on integrated inertial measurements is impractical, as sensor errors and time-varying biases lead to significant pose drift. Although recent advances have enabled inertial odometry for drone racing, existing approaches show limited generalization to trajectories not seen during training. This work improves generalization by adopting a body-frame representation and incorporating body-frame torque dynamics into the learning pipeline. The learned model predicts short-horizon relative displacements, which are fused with IMU measurements in an Extended Kalman Filter. Experimental results show that the proposed method outperforms the previous state-of-the-art learned inertial odometry approach for quadrotor pose estimation on unseen trajectories.
