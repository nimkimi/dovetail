from dovetail.hollow_test import has_hollow_test


# ---- gating: file path must look like a test file ----

def test_non_test_file_never_flagged_even_with_hollow_shape():
    added = "def test_thing():\n    pass\n"
    assert not has_hollow_test(added, "app/calc.py")


def test_test_dir_path_is_in_scope():
    added = "def test_thing():\n    pass\n"
    assert has_hollow_test(added, "tests/test_calc.py")


def test_dunder_tests_dir_path_is_in_scope():
    added = "it('does nothing', () => {\n});\n"
    assert has_hollow_test(added, "src/__tests__/calc.test.js")


def test_py_basename_pattern_is_in_scope_outside_tests_dir():
    added = "def test_thing():\n    pass\n"
    assert has_hollow_test(added, "app/test_calc.py")


def test_ts_basename_dot_test_pattern_is_in_scope():
    added = "it('does nothing', () => {\n});\n"
    assert has_hollow_test(added, "src/calc.test.ts")


def test_ts_basename_dot_spec_pattern_is_in_scope():
    added = "it('does nothing', () => {\n});\n"
    assert has_hollow_test(added, "src/calc.spec.ts")


# ---- helper files should not cue (no def test_ / it(/test( body to scan) ----

def test_conftest_with_only_fixtures_is_silent():
    added = (
        "import pytest\n\n"
        "@pytest.fixture\n"
        "def client():\n"
        "    return build_client()\n"
    )
    assert not has_hollow_test(added, "tests/conftest.py")


def test_test_helpers_file_with_no_test_functions_is_silent():
    added = "def make_user(name='a'):\n    return User(name=name)\n"
    assert not has_hollow_test(added, "tests/factories.py")


# ---- python: no real assertion at all ----

def test_python_test_with_no_assert_is_hollow():
    added = "def test_charges_user():\n    charge(user)\n"
    assert has_hollow_test(added, "tests/test_billing.py")


def test_async_python_test_with_no_assert_is_hollow():
    added = "async def test_fetches_user():\n    await fetch(user_id)\n"
    assert has_hollow_test(added, "tests/test_billing.py")


def test_python_test_with_real_assert_is_not_hollow():
    added = "def test_charges_user():\n    assert charge(user) == 42\n"
    assert not has_hollow_test(added, "tests/test_billing.py")


def test_python_test_with_pytest_raises_is_not_hollow():
    added = (
        "def test_rejects_negative_amount():\n"
        "    with pytest.raises(ValueError):\n"
        "        charge(-1)\n"
    )
    assert not has_hollow_test(added, "tests/test_billing.py")


def test_python_test_with_bare_raises_import_is_not_hollow():
    added = (
        "def test_rejects_negative_amount():\n"
        "    with raises(ValueError):\n"
        "        charge(-1)\n"
    )
    assert not has_hollow_test(added, "tests/test_billing.py")


def test_python_test_with_unittest_style_assert_is_not_hollow():
    added = (
        "def test_charges_user(self):\n"
        "    self.assertEqual(charge(user), 42)\n"
    )
    assert not has_hollow_test(added, "tests/test_billing.py")


def test_python_test_delegating_to_named_assert_helper_is_not_hollow():
    # pandas/numpy-style and custom assert_* helpers are real assertions, not
    # mock-only calls — must not be flagged just for the leading "assert_".
    added = (
        "def test_frame_matches():\n"
        "    assert_frame_equal(result, expected)\n"
    )
    assert not has_hollow_test(added, "tests/test_report.py")


def test_python_test_delegating_to_custom_assert_helper_is_not_hollow():
    added = (
        "def test_response_shape():\n"
        "    assert_valid_response(resp)\n"
    )
    assert not has_hollow_test(added, "tests/test_api.py")


# ---- python: assert True / assertTrue(True) tautology ----

def test_python_bare_assert_true_is_hollow():
    added = "def test_placeholder():\n    assert True\n"
    assert has_hollow_test(added, "tests/test_scratch.py")


def test_python_assert_true_with_message_is_hollow():
    added = 'def test_placeholder():\n    assert True, "todo"\n'
    assert has_hollow_test(added, "tests/test_scratch.py")


def test_python_asserttrue_of_true_is_hollow():
    added = "def test_placeholder(self):\n    self.assertTrue(True)\n"
    assert has_hollow_test(added, "tests/test_scratch.py")


def test_python_asserttrue_of_real_condition_is_not_hollow():
    added = "def test_is_active(self):\n    self.assertTrue(user.is_active)\n"
    assert not has_hollow_test(added, "tests/test_user.py")


def test_python_assert_true_compared_is_not_hollow():
    # `assert True == flag()` is a real (if oddly ordered) comparison, not the
    # bare-tautology shape.
    added = "def test_flag():\n    assert True == flag()\n"
    assert not has_hollow_test(added, "tests/test_flag.py")


# ---- python: assert X == X byte-identical ----

def test_python_self_equality_is_hollow():
    added = "def test_noop():\n    assert user.name == user.name\n"
    assert has_hollow_test(added, "tests/test_user.py")


def test_python_real_equality_is_not_hollow():
    added = "def test_rename():\n    assert user.name == 'Alice'\n"
    assert not has_hollow_test(added, "tests/test_user.py")


# ---- python: mock-only assertions ----

def test_python_mock_assert_called_only_is_hollow():
    added = (
        "def test_sends_email(mock_send):\n"
        "    notify(user)\n"
        "    mock_send.assert_called_once()\n"
    )
    assert has_hollow_test(added, "tests/test_notify.py")


def test_python_mock_assert_called_with_is_hollow():
    added = (
        "def test_sends_email(mock_send):\n"
        "    notify(user)\n"
        "    mock_send.assert_called_once_with(user.email)\n"
    )
    assert has_hollow_test(added, "tests/test_notify.py")


def test_python_mock_assert_plus_real_assert_is_not_hollow():
    added = (
        "def test_sends_email(mock_send):\n"
        "    result = notify(user)\n"
        "    mock_send.assert_called_once()\n"
        "    assert result.status == 'sent'\n"
    )
    assert not has_hollow_test(added, "tests/test_notify.py")


# ---- js/ts: it(/test( block with no expect( ----

def test_js_it_block_with_no_expect_is_hollow():
    added = "it('renders', () => {\n  render(<Widget />)\n});\n"
    assert has_hollow_test(added, "src/widget.test.tsx")


def test_js_test_block_with_no_expect_is_hollow():
    added = "test('renders', function () {\n  render(widget)\n});\n"
    assert has_hollow_test(added, "src/widget.test.js")


def test_js_it_block_with_real_expect_is_not_hollow():
    added = "it('renders the title', () => {\n  expect(render().title).toBe('Hi')\n});\n"
    assert not has_hollow_test(added, "src/widget.test.tsx")


def test_js_async_arrow_test_with_real_expect_is_not_hollow():
    added = "it('loads', async () => {\n  const r = await load()\n  expect(r).toEqual(42)\n});\n"
    assert not has_hollow_test(added, "src/loader.test.ts")


def test_js_test_name_with_apostrophe_still_parses():
    added = "it(\"doesn't crash\", () => {\n  render(widget)\n});\n"
    assert has_hollow_test(added, "src/widget.test.tsx")


# ---- js/ts: expect(true).toBe(true) tautology ----

def test_js_expect_true_tobe_true_is_hollow():
    added = "it('placeholder', () => {\n  expect(true).toBe(true)\n});\n"
    assert has_hollow_test(added, "src/widget.test.tsx")


# ---- js/ts: only toHaveBeenCalled-family matchers ----

def test_js_only_tohavebeencalled_is_hollow():
    added = "it('notifies', () => {\n  notify(user)\n  expect(mockSend).toHaveBeenCalled()\n});\n"
    assert has_hollow_test(added, "src/notify.test.ts")


def test_js_only_tohavebeencalledwith_is_hollow():
    added = (
        "it('notifies', () => {\n"
        "  notify(user)\n"
        "  expect(mockSend).toHaveBeenCalledWith(user.email)\n"
        "});\n"
    )
    assert has_hollow_test(added, "src/notify.test.ts")


def test_js_tohavebeenlastcalledwith_only_is_hollow():
    added = (
        "it('notifies', () => {\n"
        "  notify(user)\n"
        "  expect(mockSend).toHaveBeenLastCalledWith(user.email)\n"
        "});\n"
    )
    assert has_hollow_test(added, "src/notify.test.ts")


def test_js_mock_matcher_plus_real_matcher_is_not_hollow():
    added = (
        "it('notifies', () => {\n"
        "  const result = notify(user)\n"
        "  expect(mockSend).toHaveBeenCalledWith(user.email)\n"
        "  expect(result.ok).toBe(true)\n"
        "});\n"
    )
    assert not has_hollow_test(added, "src/notify.test.ts")


# ---- python: triple-quoted string content must not truncate the body scan ----

def test_python_test_with_column_zero_triple_quoted_content_is_not_hollow():
    added = (
        'def test_renders_template():\n'
        '    template = """\n'
        "Hello\n"
        '"""\n'
        "    assert render(template) == expected\n"
    )
    assert not has_hollow_test(added, "tests/test_render.py")


def test_python_method_with_column_zero_triple_quoted_content_is_not_hollow():
    added = (
        "class TestRender:\n"
        "    def test_renders_template(self):\n"
        '        template = """\n'
        "Hello\n"
        '"""\n'
        "        assert render(template) == expected\n"
    )
    assert not has_hollow_test(added, "tests/test_render.py")


# ---- js/ts: chained matchers (.resolves / .rejects) must still be seen ----

def test_js_resolves_tobe_is_not_hollow():
    added = "it('loads', async () => {\n  await expect(load()).resolves.toBe(1)\n});\n"
    assert not has_hollow_test(added, "src/loader.test.ts")


def test_js_rejects_tothrow_is_not_hollow():
    added = "it('rejects', async () => {\n  await expect(load()).rejects.toThrow()\n});\n"
    assert not has_hollow_test(added, "src/loader.test.ts")


def test_js_not_tohavebeencalled_is_still_mock_only():
    added = (
        "it('does not notify', () => {\n"
        "  skip(user)\n"
        "  expect(mockSend).not.toHaveBeenCalled()\n"
        "});\n"
    )
    assert has_hollow_test(added, "src/notify.test.ts")


# ---- non-code / unrecognised extension inside a test path stays silent ----

def test_unrecognised_extension_in_test_dir_is_silent():
    added = "no assertions here at all\n"
    assert not has_hollow_test(added, "tests/fixtures/data.json")


# ---- one-liner defs: the inline suite after the colon IS the body ----

def test_python_one_liner_with_real_assert_is_not_hollow():
    added = "def test_answer(): assert compute() == 42\n"
    assert not has_hollow_test(added, "tests/test_calc.py")


def test_python_one_liner_without_assert_is_still_hollow():
    added = "def test_answer(): compute()\n"
    assert has_hollow_test(added, "tests/test_calc.py")
