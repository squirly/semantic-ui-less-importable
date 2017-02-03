# Semantic UI Less Importable [![CircleCI](https://circleci.com/gh/squirly/semantic-ui-less-importable.svg?style=svg)](https://circleci.com/gh/squirly/semantic-ui-less-importable)

Derived from [Semantic UI](https://github.com/Semantic-Org/Semantic-UI/).

There are two main differences with the default Semantic UI: 
1) This version will feel more like the bootstrap less code base, such that you only need to import
the library once then you are free to structure code as desired.
2) The variables have been renamed to allow for cross component comparability. All variables are
prefixed with the component name. Eg. For buttons, `@textColor` becomes `@buttonTextColor`.

## Installation
```bash
npm install semantic-ui-less-importable
```

The versions in npm track the semantic-ui versions.

## Useage
In a less file:
```less
@import "../../node_modules/semantic-ui-less-importable/semantic";
/*
  Override variables and styles here
*/
```

## Setup
Install python 3

Install dependencies
```bash
pip install -r requirelments.txt
```

## Build
```bash
./run.py
```

Output can be found in the `dist` folder.

## Testing
The following command runs a simple smoke test of the less
```bash
node_modules/.bin/lessc dist/semantic.less > dist/semantic.css
```
And the this runs a smoke test of installation
```bash
npm install ./dist
```