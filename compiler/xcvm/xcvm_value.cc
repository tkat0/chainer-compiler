#include "compiler/xcvm/xcvm_value.h"

#include <runtime/xcvm.pb.h>

#include <compiler/type.h>
#include <compiler/value.h>

namespace oniku {
namespace xcvm {

void XCVMValue::AddOutput(runtime::XCInstructionProto* inst) {
    inst->add_outputs(id_);
    runtime::XCTypeProto* type = inst->add_output_types();
    if (value_ && value_->type().NumElements() > 0) {
        type->set_dtype(value_->type().dtype());
        for (int d : value_->type().dims()) {
            type->add_shape(d);
        }
    }
}

}  // namespace xcvm
}  // namespace oniku

