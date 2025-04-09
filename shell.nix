let
  pkgs = import <nixpkgs> {};
in pkgs.mkShell {
  packages = [
    (pkgs.python3.withPackages (python-pkgs: [
      python-pkgs.requests
      python-pkgs.flask
      python-pkgs.flask-cors
      python-pkgs.proxmoxer
    ]))
  ];

  shellHook =
  ''
    export FLASK_APP=package
    export FLASK_DEBUG=1
  '';
}

