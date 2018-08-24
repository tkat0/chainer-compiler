// Dump an ONNX proto

#include <cstdlib>
#include <fstream>
#include <iostream>
#include <limits>

#include <onnx/onnx.pb.h>

#include <common/log.h>
#include <common/protoutil.h>
#include <tools/cmdline.h>

int main(int argc, char** argv) {
    cmdline::parser args;
    args.add("full", '\0', "Dump all tensor values.");
    args.parse_check(argc, argv);

    if (args.rest().empty()) {
        QFAIL() << "Usage: " << argv[0] << " <onnx>";
    }

    for (const std::string& filename : args.rest()) {
 std::cout << "=== " << filename << " ===\n";
        onnx::ModelProto model(LoadLargeProto<onnx::ModelProto>(filename));
        onnx::GraphProto* graph = model.mutable_graph();
        if (!args.exist("full")) {
            for (int i = 0; i < graph->initializer_size(); ++i) {
                onnx::TensorProto* tensor = graph->mutable_initializer(i);
#define CLEAR_IF_LARGE(tensor, x)                                   \
                if (tensor->x().size() >= 20) tensor->clear_##x()
                CLEAR_IF_LARGE(tensor, float_data);
                CLEAR_IF_LARGE(tensor, int32_data);
                CLEAR_IF_LARGE(tensor, string_data);
                CLEAR_IF_LARGE(tensor, int64_data);
                CLEAR_IF_LARGE(tensor, raw_data);
                CLEAR_IF_LARGE(tensor, double_data);
                CLEAR_IF_LARGE(tensor, uint64_data);
            }
        }
        std::cout << model.DebugString();
    }
}
