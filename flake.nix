{
  description = "Explore reachable Python function call flow";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      supportedSystems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forAllSystems = nixpkgs.lib.genAttrs supportedSystems;
    in {
      packages = forAllSystems (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          flowgraph = pkgs.python312Packages.buildPythonApplication {
            pname = "flowgraph-cli";
            version = "0.2.1";
            pyproject = true;
            src = pkgs.lib.cleanSourceWith {
              src = self;
              filter = path: type:
                ! builtins.elem (baseNameOf path) [
                  ".flowgraph"
                  ".pytest_cache"
                  ".venv"
                  "__pycache__"
                ] && ! pkgs.lib.hasSuffix ".egg-info" (baseNameOf path);
            };
            build-system = [ pkgs.python312Packages.setuptools ];
            nativeCheckInputs = [ pkgs.python312Packages.pytestCheckHook ];
            pythonImportsCheck = [ "flowgraph" ];
          };
        in {
          default = flowgraph;
          inherit flowgraph;
        });

      apps = forAllSystems (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/flowgraph";
          meta.description = "Explore reachable Python function call flow";
        };
      });

      devShells = forAllSystems (system:
        let pkgs = nixpkgs.legacyPackages.${system};
        in {
          default = pkgs.mkShell {
            packages = [
              pkgs.python312
              pkgs.python312Packages.pytest
              pkgs.python312Packages.setuptools
            ];
          };
        });
    };
}
