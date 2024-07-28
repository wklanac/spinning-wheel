# Spinning Wheel
## Summary
This project provides Python build-time automation for the parts of
the AWS Lambda structure [prescribed by AWS](https://github.com/aws-samples/aws-secrets-manager-rotation-lambdas/blob/master/SecretsManagerRotationTemplate/lambda_function.py)
for AWS Secret Manager secret rotation which are not expected to change
between specific secret types (e.g., Active Directory user, RDS user).
That way, users only have to supply implementations for setting
and testing secrets and can maintain a smaller module.

## Implementation Details
An entrypoint is provided where the user can supply a path
to their source file containing code they want integrated with the
lambda template, as well as a desired output directory for the final result.

The lambda template repository is cloned locally and the template file is searched
for. If found, both user and template sources are parsed into [Python ASTs](https://docs.python.org/3/library/ast.html).
The syntax trees are unioned, and after this, the nodes are transformed to
flatten and deduplicate import statements, as well as to de-conflict class and function names
on a first come, first served basis. The output is then unparsed and written
to the output destination.

