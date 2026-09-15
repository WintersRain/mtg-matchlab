# Build the pinned engine

Linux/WSL; Python 3.11+, Git, JDK 17+, Maven 3.8.1+. No global configuration changes are needed. The tested toolchain is Temurin 17.0.20.1+1 and Maven 3.9.11, unpacked beneath `.local/` (ignored).

From the repository root:

```sh
mkdir -p vendor
git clone https://github.com/Card-Forge/forge.git vendor/forge
git -C vendor/forge checkout --detach b88dbd3ebd78b6aebfb2839cbbffee3102d59e30
git -C vendor/forge apply ../../patches/disable-sentry.patch
```

The one-line patch disables Sentry reporting. Do not omit it. This does not sandbox all network access. Dependency downloads require Internet access. Do not run private matches using an unrelated downloaded JAR.

With Java and Maven installed on PATH:

```sh
cd vendor/forge
mvn -B -pl forge-gui-desktop -am -DskipTests package
cd ../..
python3 -m unittest discover -s tests -v
python3 matchlab.py audit
python3 matchlab.py run --opponent aggro --seed 42 --java "$(command -v java)"
```

With the tested locally unpacked distributions:

```sh
export JAVA_HOME="$PWD/.local/jdk-17.0.20.1+1"
export PATH="$JAVA_HOME/bin:$PWD/.local/apache-maven-3.9.11/bin:$PATH"
cd vendor/forge
mvn -B -pl forge-gui-desktop -am -DskipTests package
cd ../..
python3 matchlab.py run --opponent aggro --seed 42
```

`-DskipTests` skips Forge's upstream suite during packaging; it does not establish upstream rules correctness. Our Python suite and live smoke tests are separate checks. The first build downloads dependencies and may take several minutes. The expected artifact is `forge-gui-desktop-2.0.15-SNAPSHOT-jar-with-dependencies.jar` under the module's `target/` folder.

Forge source is pinned rather than copied into this repository. Its GPL licensing and third-party card/content rights remain applicable. See `THIRD_PARTY.md`.
