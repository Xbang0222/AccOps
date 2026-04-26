"""FamilyAPI 关键纯函数测试: parse_response + extract_tokens"""
import json

from services.family_api import extract_tokens, parse_response

# ── parse_response ─────────────────────────────────────────


def test_parse_response_handles_xssi_prefix():
    """batchexecute 响应以 ")]}'" XSSI 前缀开头，应被剥离。"""
    rpc_id = "DmVhMc"
    inner = json.dumps([[1, 2, 3]])
    outer = json.dumps([["wrb.fr", rpc_id, inner, None, None, "generic"]])
    text = ")]}'\n34\n" + outer

    result = parse_response(text, rpc_id)
    assert result == [[1, 2, 3]]


def test_parse_response_returns_none_when_rpc_id_missing():
    text = ")]}'\n34\n" + json.dumps([["wrb.fr", "OTHER_RPC", "[]", None, None, "generic"]])
    assert parse_response(text, "DmVhMc") is None


def test_parse_response_returns_none_for_malformed_json():
    text = ")]}'\nnot-valid-json\n"
    assert parse_response(text, "DmVhMc") is None


def test_parse_response_skips_numeric_lines():
    """batchexecute 在数据帧之间会插入数字 (chunk size)，应跳过。"""
    rpc_id = "V2esPe"
    inner = json.dumps({"members": ["a", "b"]})
    outer = json.dumps([["wrb.fr", rpc_id, inner, None, None, "generic"]])
    text = ")]}'\n42\n" + outer + "\n100\n"

    result = parse_response(text, rpc_id)
    assert result == {"members": ["a", "b"]}


def test_parse_response_handles_inline_json_payload():
    """内层数据有时是已解析的对象，而非字符串。"""
    rpc_id = "Csu7b"
    outer = json.dumps([["wrb.fr", rpc_id, [1, 2, 3], None, None, "generic"]])
    text = ")]}'\n" + outer

    result = parse_response(text, rpc_id)
    assert result == [1, 2, 3]


# ── extract_tokens ─────────────────────────────────────────


def test_extract_tokens_finds_all_three():
    # 真实 WIZ_global_data 是紧凑 JSON，无空格
    html = 'var WIZ_global_data = {"SNlM0e":"AT-TOKEN-VALUE","FdrFJe":"FSID-VALUE","cfb2h":"BL-VALUE"};'
    tokens = extract_tokens(html)
    assert tokens == {
        "at": "AT-TOKEN-VALUE",
        "f.sid": "FSID-VALUE",
        "bl": "BL-VALUE",
    }


def test_extract_tokens_returns_empty_when_no_match():
    assert extract_tokens("<html><body>nothing here</body></html>") == {}


def test_extract_tokens_handles_partial_match():
    """只有 at 没有其他时，应只返回 at。"""
    tokens = extract_tokens('"SNlM0e":"only-at"')
    assert tokens == {"at": "only-at"}
