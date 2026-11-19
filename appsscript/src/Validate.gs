// ---------- Validate: request checks ----------
//
// A failed check is a 422 whose detail is a list of problems, [{"type", "loc", "msg", "input"}]. The app shows any
// list as a generic error; the other errors carry a code it translates. Text is not coerced: a number where text is
// expected is an error. Integers may come as "3".

const LANGS_ = ['en', 'hi', 'mr'];

const F_ = {
  str: (opts) => Object.assign({ type: 'str' }, opts || {}),
  int: (opts) => Object.assign({ type: 'int' }, opts || {}),
  oneOf: (values, opts) => Object.assign({ type: 'enum', values: values }, opts || {}),
  /** A list of objects, each checked against `fields`. */
  list: (fields, opts) => Object.assign({ type: 'list', fields: fields }, opts || {}),
};
const REQUIRED_ = { required: true };

const BODY_ = {
  signup: {
    name: F_.str({ required: true, min: 1, max: 80 }),
    phone: F_.str(REQUIRED_),
    password: F_.str({ required: true, min: 6, max: 200 }),
    role: F_.oneOf(['student', 'teacher'], { def: 'student' }),
    code: F_.str({ def: '' }),
    lang: F_.oneOf(LANGS_, { def: 'en' }),
  },
  login: { phone: F_.str(REQUIRED_), password: F_.str(REQUIRED_) },
  me: {
    name: F_.str({ min: 1, max: 80, nullable: true, def: null }),
    lang: F_.oneOf(LANGS_, { nullable: true, def: null }),
  },
  checkin: { phase: F_.oneOf(['before', 'after'], REQUIRED_), mood: F_.int({ required: true, ge: 1, le: 5 }) },
  feedback: { screen: F_.str({ required: true, max: 40 }), text: F_.str({ required: true, min: 1, max: 2000 }) },
  link: { meet_link: F_.str(REQUIRED_) },
  settings: { group_link: F_.str({ nullable: true, def: null }) },
  place: { batch: F_.str({ required: true, min: 1, max: 40 }), note: F_.str({ nullable: true, def: null, max: 300 }) },
  status: { status: F_.oneOf(['approved', 'rejected'], REQUIRED_) },
  shared: { text: F_.str({ required: true, min: 1, max: 500 }) },
  curriculum: { curriculum: F_.str({ required: true, min: 1, max: 40 }) },
  itemFeedback: { item: F_.str({ required: true, min: 1, max: 40 }), text: F_.str({ required: true, min: 1, max: 1000 }) },
  practice: {
    entries: F_.list({
      item: F_.str({ required: true, min: 1, max: 40 }),
      reaction: F_.int({ nullable: true, def: null, ge: 1, le: 4 }),
      pain: F_.int({ def: 0, ge: 0, le: 1 }),
      note: F_.str({ nullable: true, def: null, max: 500 }),
    }, { required: true, max: 60 }),
  },
  solo: {
    minutes: F_.int({ required: true, ge: 0, le: 240 }),
    entries: F_.list({
      item: F_.str({ required: true, min: 1, max: 40 }),
      hold_s: F_.int({ nullable: true, def: null, ge: 0, le: 3600 }),
      reaction: F_.int({ nullable: true, def: null, ge: 1, le: 4 }),
      pain: F_.int({ def: 0, ge: 0, le: 1 }),
      note: F_.str({ nullable: true, def: null, max: 500 }),
    }, { required: true, max: 60 }),
  },
};

const QUERY_LANG_ = { lang: F_.oneOf(LANGS_, { def: 'en' }) };
// A 422 names the parameter, so they carry their names.
const PATH_SESSION_ = { session_id: F_.int(REQUIRED_) };
const PATH_USER_ = { user_id: F_.int(REQUIRED_) };
const PATH_BATCH_ = { key: F_.str({ required: true, min: 1, max: 40 }) };
const PATH_ITEM_ = { item: F_.str({ required: true, min: 1, max: 40 }) };

function validateBody_(fields, body, errors) {
  if (body === null || body === undefined) {
    errors.push({ type: 'missing', loc: ['body'], msg: 'Field required', input: null });
    return null;
  }
  if (typeof body !== 'object' || Array.isArray(body)) {
    errors.push({ type: 'model_attributes_type', loc: ['body'], msg: 'Input should be a valid dictionary or object to extract fields from', input: body });
    return null;
  }
  return validateFields_(fields, body, ['body'], errors);
}

function validateFields_(fields, source, loc, errors) {
  const out = {};
  Object.keys(fields).forEach((name) => {
    const field = fields[name];
    const where = loc.concat([name]);
    const has = source && Object.prototype.hasOwnProperty.call(source, name) && source[name] !== undefined;
    if (!has) {
      if (field.required) errors.push({ type: 'missing', loc: where, msg: 'Field required', input: source || null });
      else out[name] = field.def;
      return;
    }
    const value = source[name];
    if (value === null && field.nullable) {
      out[name] = null;
      return;
    }
    if (field.type === 'list') {
      out[name] = validateList_(field, value, where, errors);
      return;
    }
    const fromQuery = loc[0] !== 'body'; // query and path values arrive as text
    const result = coerce_(field, value, fromQuery);
    if (result.error) errors.push(Object.assign({ loc: where, input: value }, result.error));
    else out[name] = result.value;
  });
  return out;
}

function validateList_(field, value, loc, errors) {
  if (!Array.isArray(value)) {
    errors.push({ type: 'list_type', loc: loc, msg: 'Input should be a valid list', input: value });
    return null;
  }
  if (field.max !== undefined && value.length > field.max) {
    errors.push({ type: 'too_long', loc: loc, msg: 'List should have at most ' + plural_(field.max, 'item'), input: value, ctx: { max_length: field.max } });
    return null;
  }
  return value.map((item, i) => {
    if (item === null || typeof item !== 'object' || Array.isArray(item)) {
      errors.push({ type: 'model_type', loc: loc.concat([i]), msg: 'Input should be an object', input: item });
      return null;
    }
    return validateFields_(field.fields, item, loc.concat([i]), errors);
  });
}

function coerce_(field, value, fromText) {
  if (field.type === 'str') {
    if (typeof value !== 'string') return { error: { type: 'string_type', msg: 'Input should be a valid string' } };
    const length = Array.from(value).length;
    if (field.min !== undefined && length < field.min) {
      return { error: { type: 'string_too_short', msg: 'String should have at least ' + plural_(field.min, 'character'), ctx: { min_length: field.min } } };
    }
    if (field.max !== undefined && length > field.max) {
      return { error: { type: 'string_too_long', msg: 'String should have at most ' + plural_(field.max, 'character'), ctx: { max_length: field.max } } };
    }
    return { value: value };
  }
  if (field.type === 'enum') {
    if (field.values.indexOf(value) < 0) {
      const names = field.values.map((v) => "'" + v + "'");
      const msg = 'Input should be ' + (names.length > 1 ? names.slice(0, -1).join(', ') + ' or ' + names[names.length - 1] : names[0]);
      return { error: { type: 'literal_error', msg: msg, ctx: { expected: names.join(', ') } } };
    }
    return { value: value };
  }
  if (field.type === 'int') {
    let number;
    if (typeof value === 'number') {
      if (!isFinite(value)) return { error: { type: 'int_type', msg: 'Input should be a finite number' } };
      if (Math.floor(value) !== value) return { error: { type: 'int_from_float', msg: 'Input should be a valid integer, got a number with a fractional part' } };
      number = value;
    } else if (typeof value === 'boolean' && !fromText) {
      number = value ? 1 : 0;
    } else if (typeof value === 'string' && /^\s*[+-]?\d+\s*$/.test(value)) {
      number = parseInt(value, 10);
    } else if (typeof value === 'string') {
      return { error: { type: 'int_parsing', msg: 'Input should be a valid integer, unable to parse string as an integer' } };
    } else {
      return { error: { type: 'int_type', msg: 'Input should be a valid integer' } };
    }
    if (field.ge !== undefined && number < field.ge) {
      return { error: { type: 'greater_than_equal', msg: 'Input should be greater than or equal to ' + field.ge, ctx: { ge: field.ge } } };
    }
    if (field.le !== undefined && number > field.le) {
      return { error: { type: 'less_than_equal', msg: 'Input should be less than or equal to ' + field.le, ctx: { le: field.le } } };
    }
    return { value: number };
  }
  throw new Error('unknown field type ' + field.type);
}

function plural_(n, word) {
  return n + ' ' + word + (n === 1 ? '' : 's');
}
