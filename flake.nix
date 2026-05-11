{
	# Description
	description = "Secrets Manager";

	# Inputs
	inputs = {
		nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
		flake-utils.url = "github:numtide/flake-utils";
	};

	# Outputs
	outputs = {self, nixpkgs, flake-utils, ...}: flake-utils.lib.eachDefaultSystem(system: let
		# Packages
		pkgs = import nixpkgs {
			inherit system;
		};
	in {
		# Devshells
		devShells.default = pkgs.mkShell {
			name = "tlck";
			nativeBuildInputs = with pkgs; [
				wrapGAppsHook4
				gobject-introspection
			];
			packages = with pkgs; [
				gtk4
				cairo
				pkg-config
				libadwaita
				adwaita-icon-theme
			];
		};
	});
}
