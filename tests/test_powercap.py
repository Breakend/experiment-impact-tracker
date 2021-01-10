# Code in file tensor/two_layer_net_tensor.py
import time

import torch

from experiment_impact_tracker.cpu.powercap import (PowerGadget,
                                                    is_powercap_compatible)


def _helper_function():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # N is batch size; D_in is input dimension;
    # H is hidden dimension; D_out is output dimension.
    N, D_in, H, D_out = 1024, 10000, 1000, 100

    # Create random input and output data
    x = torch.randn(N, D_in, device=device)
    y = torch.randn(N, D_out, device=device)

    # Randomly initialize weights
    w1 = torch.randn(D_in, H, device=device)
    w2 = torch.randn(H, D_out, device=device)

    learning_rate = 1e-6
    for t in range(50):
        # Forward pass: compute predicted y
        h = x.mm(w1)
        h_relu = h.clamp(min=0)
        y_pred = h_relu.mm(w2)

        # Compute and print loss; loss is a scalar, and is stored in a PyTorch Tensor
        # of shape (); we can get its value as a Python number with loss.item().
        loss = (y_pred - y).pow(2).sum()
        print(t, loss.item())

        # Backprop to compute gradients of w1 and w2 with respect to loss
        grad_y_pred = 2.0 * (y_pred - y)
        grad_w2 = h_relu.t().mm(grad_y_pred)
        grad_h_relu = grad_y_pred.mm(w2.t())
        grad_h = grad_h_relu.clone()
        grad_h[h < 0] = 0
        grad_w1 = x.t().mm(grad_h)

        # Update weights using gradient descent
        w1 -= learning_rate * grad_w1
        w2 -= learning_rate * grad_w2


def test_powercap():
    if is_powercap_compatible():
        gadget = PowerGadget()
        gadget.start()
        time.sleep(1)
        results = gadget.join()
        assert "Processor Power_0(Watt)" in results.keys()
