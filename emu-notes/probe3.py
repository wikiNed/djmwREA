import frida, sys, json, time

PID = 2808

JS = r"""
var results = {};

// il2cpp 导出
function findExport(mod, name) {
    return Module.findExportByName(mod, name);
}

// 遍历所有模块里名为 libil2cpp.so 的
function il2mod() {
    var m = Process.findModuleByName("libil2cpp.so");
    return m;
}

rpc.exports = {};

setTimeout(function () {
    try {
        var m = il2mod();
        var out = {};
        out.module = m ? { name: m.name, base: m.base.toString(), size: m.size } : null;
        if (m) {
            var names = ["il2cpp_domain_get", "il2cpp_domain_get_assemblies",
                         "il2cpp_assembly_get_image", "il2cpp_class_from_name",
                         "il2cpp_class_get_field_from_name", "il2cpp_field_get_offset",
                         "il2cpp_field_static_get_value", "il2cpp_image_get_name",
                         "il2cpp_string_new", "il2cpp_object_unbox",
                         "il2cpp_gchandle_get_target", "il2cpp_gchandle_new"];
            out.exports = {};
            names.forEach(function (n) {
                var p = Module.findExportByName("libil2cpp.so", n);
                out.exports[n] = p ? p.toString() : null;
            });
        }
        send({ type: "modinfo", data: out });
    } catch (e) {
        send({ type: "error", data: String(e) });
    }
}, 800);
"""

def on_message(msg, data):
    d = msg.get("payload")
    if d:
        if d.get("type") == "modinfo":
            print("=== libil2cpp 信息 ===")
            print(json.dumps(d["data"], indent=2, ensure_ascii=False))
        elif d.get("type") == "error":
            print("ERROR:", d["data"])

dev = frida.get_device_manager().add_remote_device("127.0.0.1:27042")
sess = dev.attach(PID)
script = sess.create_script(JS)
script.on("message", on_message)
script.load()
time.sleep(6)
sess.detach()
