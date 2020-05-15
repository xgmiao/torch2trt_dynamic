from torch2trt.torch2trt import *
from torch2trt.module_test import add_module_test
from .size import IntWarper


@tensorrt_converter('torch.Tensor.reshape')
@tensorrt_converter('torch.Tensor.view')
def convert_view(ctx):
    support_dynamic_shape = False
    if hasattr(ctx, "support_dynamic_shape"):
        support_dynamic_shape = ctx.support_dynamic_shape
        
    input = ctx.method_args[0]
    size = get_arg(ctx, 'shape', pos=1, default=[])
    if isinstance(size, int):
        size = tuple(ctx.method_args[1:])
    input_trt = trt_(ctx.network, input)
    output = ctx.method_return

    ## check if there are shape tensor
    is_shape_tensor = False
    for s in size:
        if isinstance(s, IntWarper):
            is_shape_tensor = True
            break

    ## negative shape might cause overflow, forbid for now
    for s in size:
        if s<0:
            is_shape_tensor=True
            break

    ## compute shape tensor
    if support_dynamic_shape and is_shape_tensor:
        shape_trt = []
        for idx, s in enumerate(size):
            if isinstance(s, IntWarper):
                shape_trt.append(s._trt)
            else:
                if s<0:
                    print("warning: negative index of view/reshape might cause overflow!")
                const_shape_trt = trt_(ctx.network, input.new_tensor([s],dtype=torch.int32))
                shape_trt.append(const_shape_trt)

        shape_trt = ctx.network.add_concatenation(shape_trt).get_output(0)

    layer = ctx.network.add_shuffle(input_trt)
    if support_dynamic_shape and is_shape_tensor:
        layer.set_input(1, shape_trt)
    elif support_dynamic_shape:
        layer.reshape_dims = output.shape
    else:
        layer.reshape_dims = tuple(output.shape[1:])
    output._trt = layer.get_output(0)



class View(torch.nn.Module):
    def __init__(self, *dims):
        super(View, self).__init__()
        self.dims = dims

    def forward(self, x):
        return x.view(*self.dims)



@add_module_test(torch.float32, torch.device('cuda'), [(1, 3)])
@add_module_test(torch.float32, torch.device('cuda'), [(1, 3, 3)])
@add_module_test(torch.float32, torch.device('cuda'), [(1, 3, 3, 3)])
def test_view_1d():
    return View(1, -1)


@add_module_test(torch.float32, torch.device('cuda'), [(1, 3)])
@add_module_test(torch.float32, torch.device('cuda'), [(1, 3, 3)])
@add_module_test(torch.float32, torch.device('cuda'), [(1, 3, 3, 3)])
def test_view_2d():
    return View(1, 1, -1)


@add_module_test(torch.float32, torch.device('cuda'), [(1, 3)])
@add_module_test(torch.float32, torch.device('cuda'), [(1, 3, 3)])
@add_module_test(torch.float32, torch.device('cuda'), [(1, 3, 3, 3)])
def test_view_3d():
    return View(1, 1, 1, -1)
