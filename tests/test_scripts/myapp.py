# code from pytorch tutorials
# https://github.com/pytorch/tutorials/blob/master/beginner_source/examples_tensor/two_layer_net_tensor.py
import os
import sys
import tempfile

import torch

from experiment_impact_tracker.compute_tracker import ImpactTracker


def train(d: str = "cpu", log_dir: str = tempfile.mkdtemp()):
    tracker = ImpactTracker( os.path.join( log_dir, "" ) )

    tracker.launch_impact_monitor()
    device = torch.device( d )

    # N is batch size; D_in is input dimension;
    # H is hidden dimension; D_out is output dimension.
    N, D_in, H, D_out = 1024, 10000, 1000, 100

    # Create random input and output data
    x = torch.randn( N, D_in, device=device )
    y = torch.randn( N, D_out, device=device )

    # Randomly initialize weights
    w1 = torch.randn( D_in, H, device=device )
    w2 = torch.randn( H, D_out, device=device )

    learning_rate = 1e-6
    for t in range(10):
        # Forward pass: compute predicted y
        h = x.mm( w1 )
        h_relu = h.clamp( min=0 )
        y_pred = h_relu.mm( w2 )

        # Backprop to compute gradients of w1 and w2 with respect to loss
        grad_y_pred = 2.0 * (y_pred - y)
        grad_w2 = h_relu.t().mm( grad_y_pred )
        grad_h_relu = grad_y_pred.mm( w2.t() )
        grad_h = grad_h_relu.clone()
        grad_h[h < 0] = 0
        grad_w1 = x.t().mm( grad_h )

        # Update weights using gradient descent
        w1 -= learning_rate * grad_w1
        w2 -= learning_rate * grad_w2
        tracker.get_latest_info_and_check_for_errors()

    print("SUCCESS")


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        train( sys.argv[1], sys.argv[2] )
    else:
        train()
